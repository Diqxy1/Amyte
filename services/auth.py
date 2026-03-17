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
    client_version: str  # necessário para X-Riot-ClientVersion
    discord_name: str = ""  # nome Discord — fallback se game_name não vier


async def authenticate_with_ssid(
    ssid: str,
    session: aiohttp.ClientSession,
    discord_name: str = "",
) -> RiotTokens:
    """
    Autentica via cookie ssid e retorna tokens com cid=riot-client,
    necessários para acessar a API da loja do Valorant.
    """

    # Busca versão do cliente em paralelo com a autenticação
    access_token, client_version = await asyncio.gather(
        _fetch_riot_client_token(ssid, session),
        _fetch_client_version(session),
    )

    payload = _decode_jwt_payload(access_token)
    cid = payload.get("cid", "unknown")
    log.info("Token obtido — cid=%s sub=%s", cid, payload.get("sub", "?"))

    entitlements_token = await _fetch_entitlements(access_token, session)

    user_id = payload.get("sub", "")

    # Tenta extrair do payload primeiro (token web tem acct, riot-client não tem)
    acct      = payload.get("acct", {})
    game_name = acct.get("game_name", "")
    tag_line  = acct.get("tag_line", "")

    # Se não veio no payload, busca via name-service do PD
    if not game_name:
        game_name, tag_line = await _fetch_name_from_pd(
            access_token, entitlements_token, client_version, user_id, session
        )

    return RiotTokens(
        access_token=access_token,
        entitlements_token=entitlements_token,
        user_id=user_id,
        game_name=game_name or "Agente",
        tag_line=tag_line,
        client_version=client_version,
        discord_name=discord_name,
    )


async def _fetch_client_version(session: aiohttp.ClientSession) -> str:
    """Busca a versão atual do Riot Client via valorant-api.com."""
    try:
        async with session.get(_VERSION_URL) as r:
            data = await r.json(content_type=None)
        version = data["data"]["riotClientVersion"]
        log.info("Client version: %s", version)
        return version
    except Exception as exc:
        log.warning("Falha ao buscar client version: %s — usando fallback", exc)
        return "release-09.11-shipping-24-2600985"


async def _fetch_riot_client_token(ssid: str, session: aiohttp.ClientSession) -> str:
    """Troca o ssid por um access_token com cid=riot-client em duas etapas."""
    cookies = {"ssid": ssid}

    # Etapa 1 — inicia o fluxo com client_id=riot-client
    init_payload = {
        "acr_values": "urn:riot:bronze",
        "claims": "",
        "client_id": "riot-client",
        "nonce": "oYnVwCSrdompeBzJFZXZiBHR",
        "redirect_uri": "http://localhost/redirect",
        "response_type": "token id_token",
        "scope": "openid link ban lol_region account",
    }

    async with session.post(
        _AUTH_URL,
        json=init_payload,
        headers=_HEADERS,
        cookies=cookies,
        allow_redirects=False,
    ) as resp:
        init_data = await resp.json(content_type=None)
        resp_cookies = {k: v.value for k, v in resp.cookies.items()}

    log.debug("Etapa 1 — type=%s", init_data.get("type"))

    if init_data.get("type") == "response":
        uri = init_data["response"]["parameters"]["uri"]
        return _extract_access_token_from_uri(uri)

    if init_data.get("type") == "error":
        raise InvalidCookieError("Cookie ssid inválido ou expirado. Obtenha um novo ssid.")

    if init_data.get("type") != "auth":
        raise AuthenticationError(
            f"Resposta inesperada na etapa 1 (type={init_data.get('type')!r})"
        )

    # Etapa 2 — completa o fluxo reusando o ssid nos cookies
    merged = {"ssid": ssid, **resp_cookies}

    async with session.put(
        _AUTH_URL,
        json={"language": "pt_BR", "remember": True, "type": "auth"},
        headers=_HEADERS,
        cookies=merged,
        allow_redirects=False,
    ) as resp:
        complete_data = await resp.json(content_type=None)

    log.debug("Etapa 2 — type=%s", complete_data.get("type"))

    if complete_data.get("type") == "response":
        uri = complete_data["response"]["parameters"]["uri"]
        return _extract_access_token_from_uri(uri)

    if complete_data.get("type") == "error":
        raise InvalidCookieError(
            f"Falha na auth ({complete_data.get('error', '?')}). O ssid pode ter expirado."
        )

    raise AuthenticationError(
        f"Resposta inesperada na etapa 2 (type={complete_data.get('type')!r}): {complete_data}"
    )


def _decode_jwt_payload(token: str) -> dict:
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        return _json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise AuthenticationError(f"Falha ao decodificar JWT: {exc}") from exc


def _extract_access_token_from_uri(uri: str) -> str:
    fragment = urllib.parse.urlparse(uri).fragment
    params   = urllib.parse.parse_qs(fragment)
    try:
        return params["access_token"][0]
    except (KeyError, IndexError) as exc:
        raise AuthenticationError("access_token não encontrado na URI de redirect.") from exc


async def _fetch_entitlements(access_token: str, session: aiohttp.ClientSession) -> str:
    headers = {**_HEADERS, "Authorization": f"Bearer {access_token}"}
    async with session.post(_ENTITLEMENTS_URL, headers=headers, json={}) as resp:
        data = await resp.json(content_type=None)
    try:
        return data["entitlements_token"]
    except KeyError as exc:
        raise AuthenticationError("Falha ao obter entitlements_token.") from exc


async def _fetch_name_from_pd(
    access_token: str,
    entitlements_token: str,
    client_version: str,
    user_id: str,
    session: aiohttp.ClientSession,
) -> tuple[str, str]:
    """
    Busca game_name e tag_line via name-service do PD.
    Usa a região BR como padrão — funciona para lookup por PUUID.
    """
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
        url = "https://pd.na.a.pvp.net/name-service/v2/players"
        async with session.put(url, headers=headers, json=[user_id]) as r:
            if r.status == 200:
                data = await r.json(content_type=None)
                if data and isinstance(data, list):
                    player = data[0]
                    game_name = player.get("GameName", "")
                    tag_line  = player.get("TagLine", "")
                    if game_name:
                        log.info("Nome obtido via name-service: %s#%s", game_name, tag_line)
                        return game_name, tag_line
            log.warning("name-service retornou %s", r.status)
    except Exception as exc:
        log.warning("Falha ao buscar nome via name-service: %s", exc)
    return "", ""