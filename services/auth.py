import asyncio
import base64
import json as _json
import logging
import urllib.parse
from dataclasses import dataclass

import aiohttp

log = logging.getLogger(__name__)

_AUTH_URL         = "https://auth.riotgames.com/api/v1/authorization"
_ENTITLEMENTS_URL = "https://entitlements.auth.riotgames.com/api/token/v1"
_VERSION_URL      = "https://valorant-api.com/v1/version"

_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "RiotClient/60.0.6.4770705.4749685 rso-auth (Windows;10;;Professional, x64)",
    "Accept": "application/json",
}


class AuthenticationError(Exception):
    """Erro genérico de autenticação com a Riot."""


class InvalidCookieError(AuthenticationError):
    """Cookie ssid inválido ou expirado."""


@dataclass(frozen=True)
class RiotTokens:
    access_token: str
    entitlements_token: str
    user_id: str
    game_name: str
    tag_line: str
    client_version: str
    discord_name: str = ""


async def authenticate_with_ssid(
    ssid: str,
    session: aiohttp.ClientSession,
    discord_name: str = "",
) -> RiotTokens:
    """
    Autentica via cookie ssid usando play-valorant-web-prod.
    Aceita o valor raw do ssid ou um JWT (extrai o valor interno).
    """
    ssid = _extract_ssid_value(ssid.strip())

    access_token, client_version = await asyncio.gather(
        _fetch_token(ssid, session),
        _fetch_client_version(session),
    )

    entitlements_token = await _fetch_entitlements(access_token, session)

    payload   = _decode_jwt_payload(access_token)
    user_id   = payload.get("sub", "")
    acct      = payload.get("acct", {})
    game_name = acct.get("game_name", "")
    tag_line  = acct.get("tag_line", "")

    # Se o token web não trouxer game_name, busca via name-service
    if not game_name:
        game_name, tag_line = await _fetch_name(
            access_token, entitlements_token, client_version, user_id, session
        )

    log.info("Auth ok — cid=%s user=%s#%s", payload.get("cid"), game_name, tag_line)

    return RiotTokens(
        access_token=access_token,
        entitlements_token=entitlements_token,
        user_id=user_id,
        game_name=game_name or "",
        tag_line=tag_line or "",
        client_version=client_version,
        discord_name=discord_name,
    )


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _extract_ssid_value(raw: str) -> str:
    """
    Extrai o valor real do ssid.
    Se for um JWT (eyJ...), pega o campo 'ssid' do payload.
    """
    if raw.startswith("eyJ") and raw.count(".") == 2:
        try:
            p = raw.split(".")[1]
            p += "=" * (-len(p) % 4)
            payload = _json.loads(base64.urlsafe_b64decode(p).decode("utf-8"))
            if "ssid" in payload:
                log.info("ssid é JWT, extraindo valor interno...")
                return payload["ssid"]
        except Exception as exc:
            log.warning("Falha ao extrair ssid do JWT: %s", exc)
    return raw


async def _fetch_token(raw_input: str, session: aiohttp.ClientSession) -> str:
    """
    Obtém access_token a partir do input do usuário.

    Aceita dois formatos:
      1. Cookie ssid (valor raw ou JWT) — faz o fluxo OAuth
      2. __Secure-access_token direto (JWT longo) — usa diretamente

    O __Secure-access_token é preferível porque não depende de IP
    e não precisa de etapa 2, evitando auth_failure em servidores fora do BR.
    """
    # Se o input tiver 3 partes JWT e for longo (>200 chars), é um access_token direto
    parts = raw_input.split(".")
    if len(parts) == 3 and len(raw_input) > 200:
        try:
            payload = _decode_jwt_payload(raw_input)
            cid = payload.get("cid", "")
            log.info("Access token direto detectado — cid=%s", cid)
            return raw_input
        except Exception:
            pass

    # Caso contrário, trata como ssid e faz o fluxo OAuth
    ssid = raw_input

    payload = {
        "client_id": "play-valorant-web-prod",
        "nonce": "1",
        "redirect_uri": "https://playvalorant.com/opt_in",
        "response_type": "token id_token",
        "scope": "account openid",
    }

    async with session.post(
        _AUTH_URL,
        json=payload,
        headers=_HEADERS,
        cookies={"ssid": ssid},
        allow_redirects=False,
    ) as resp:
        data = await resp.json(content_type=None)
        resp_cookies = {k: v.value for k, v in resp.cookies.items()}

    log.info("Etapa 1 type=%s error=%s", data.get("type"), data.get("error"))

    if data.get("type") == "response":
        return _extract_token_from_uri(data["response"]["parameters"]["uri"])

    if data.get("type") == "error":
        raise InvalidCookieError(
            "Cookie ssid inválido ou expirado.\n"
            "Tente usar o __Secure-access_token diretamente (veja as instruções)."
        )

    if data.get("type") != "auth":
        raise AuthenticationError(f"Resposta inesperada: type={data.get('type')!r}")

    merged = {"ssid": ssid, **resp_cookies}

    async with session.put(
        _AUTH_URL,
        json={"language": "pt_BR", "remember": True, "type": "auth"},
        headers=_HEADERS,
        cookies=merged,
        allow_redirects=False,
    ) as resp2:
        data2 = await resp2.json(content_type=None)

    log.info("Etapa 2 type=%s error=%s", data2.get("type"), data2.get("error"))

    if data2.get("type") == "response":
        return _extract_token_from_uri(data2["response"]["parameters"]["uri"])

    raise InvalidCookieError(
        "Autenticação falhou (possível bloqueio por IP do servidor).\n"
        "Use o __Secure-access_token diretamente:\n"
        "DevTools → Application → Cookies → auth.riotgames.com → __Secure-access_token"
    )


async def _fetch_client_version(session: aiohttp.ClientSession) -> str:
    try:
        async with session.get(_VERSION_URL) as r:
            data = await r.json(content_type=None)
        version = data["data"]["riotClientVersion"]
        log.info("Client version: %s", version)
        return version
    except Exception as exc:
        log.warning("Falha ao buscar client version: %s", exc)
        return "release-09.11-shipping-24-2600985"


async def _fetch_entitlements(access_token: str, session: aiohttp.ClientSession) -> str:
    headers = {**_HEADERS, "Authorization": f"Bearer {access_token}"}
    async with session.post(_ENTITLEMENTS_URL, headers=headers, json={}) as resp:
        data = await resp.json(content_type=None)
    try:
        return data["entitlements_token"]
    except KeyError as exc:
        raise AuthenticationError("Falha ao obter entitlements_token.") from exc


async def _fetch_name(
    access_token: str,
    entitlements_token: str,
    client_version: str,
    user_id: str,
    session: aiohttp.ClientSession,
) -> tuple[str, str]:
    """Busca game_name e tag_line via name-service."""
    _CLIENT_PLATFORM = (
        "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9y"
        "bU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVu"
        "a25vd24iDQp9"
    )
    headers = {
        **_HEADERS,
        "Authorization": f"Bearer {access_token}",
        "X-Riot-Entitlements-JWT": entitlements_token,
        "X-Riot-ClientVersion": client_version,
        "X-Riot-ClientPlatform": _CLIENT_PLATFORM,
    }
    try:
        async with session.put(
            "https://pd.na.a.pvp.net/name-service/v2/players",
            headers=headers,
            json=[user_id],
        ) as r:
            if r.status == 200:
                data = await r.json(content_type=None)
                if data and isinstance(data, list):
                    p = data[0]
                    name = p.get("GameName", "")
                    tag  = p.get("TagLine", "")
                    if name:
                        log.info("Nome obtido: %s#%s", name, tag)
                        return name, tag
    except Exception as exc:
        log.warning("Falha ao buscar nome: %s", exc)
    return "", ""


def _decode_jwt_payload(token: str) -> dict:
    try:
        p = token.split(".")[1]
        p += "=" * (-len(p) % 4)
        return _json.loads(base64.urlsafe_b64decode(p).decode("utf-8"))
    except Exception as exc:
        raise AuthenticationError(f"Falha ao decodificar JWT: {exc}") from exc


def _extract_token_from_uri(uri: str) -> str:
    fragment = urllib.parse.urlparse(uri).fragment
    params   = urllib.parse.parse_qs(fragment)
    try:
        return params["access_token"][0]
    except (KeyError, IndexError) as exc:
        raise AuthenticationError("access_token não encontrado na URI.") from exc