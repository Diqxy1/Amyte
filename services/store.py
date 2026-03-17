import asyncio
import logging
from dataclasses import dataclass, field

import aiohttp

from config import settings
from services.auth import RiotTokens

log = logging.getLogger(__name__)

_CLIENT_PLATFORM = (
    "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9y"
    "bU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVu"
    "a25vd24iDQp9"
)

# IDs de moeda
_VP_ID = "85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741"
_RAD_ID = "e59aa87c-4cbf-517a-5983-6e81511be9b7"
_KC_ID = "85ca954a-41f2-ce94-9b45-8ca3dd39a00d"


@dataclass(frozen=True)
class SkinOffer:
    uuid: str
    name: str
    image_url: str | None
    price: int


@dataclass(frozen=True)
class NightMarketOffer:
    uuid: str
    name: str
    image_url: str | None
    original_price: int
    final_price: int
    discount_percent: int


@dataclass(frozen=True)
class StoreData:
    skins: list
    night_market: list = field(default_factory=list)
    has_night_market: bool = False


@dataclass(frozen=True)
class WalletData:
    vp: int
    radianite: int
    kingdom_credits: int


@dataclass(frozen=True)
class RankData:
    tier_name: str
    tier_icon: str | None
    rr: int
    leaderboard_rank: int
    wins: int
    peak_tier_name: str
    peak_tier_icon: str | None



# ItemTypeID → nome amigável
_ITEM_TYPE_NAMES = {
    "d5f120f8-ff8c-4aac-92ea-f2b5acbe6838": "Spray",
    "3f296c07-64c3-494c-923b-fe692a4fa1bd": "Player Card",
    "de7caa6b-adf7-4588-aebd-ad8c14603191": "Player Title",
    "dd3bf334-87f3-40bd-b043-682a57a8dc3a": "Gun Buddy",
}


@dataclass(frozen=True)
class KCOffer:
    uuid: str
    name: str
    image_url: str | None
    price: int
    item_type: str  # Spray, Player Card, etc.


@dataclass(frozen=True)
class KCStoreData:
    offers: list
    remaining_seconds: int

    @property
    def remaining_hours(self) -> int:
        return self.remaining_seconds // 3600

class StoreService:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ #
    #  API pública                                                         #
    # ------------------------------------------------------------------ #

    async def fetch_store(self, tokens: RiotTokens, region: str) -> StoreData:
        pd_base = self._resolve_pd_url(region)
        headers = self._build_headers(tokens)
        storefront = await self._fetch_storefront_v3(pd_base, tokens.user_id, headers)
        log.debug("Storefront keys: %s", list(storefront.keys()))
        skins = await self._build_store_offers(storefront)
        night_market = await self._build_night_market(storefront)
        return StoreData(skins=list(skins), night_market=list(night_market), has_night_market=bool(night_market))

    async def fetch_wallet(self, tokens: RiotTokens, region: str) -> WalletData:
        pd_base = self._resolve_pd_url(region)
        headers = self._build_headers(tokens)
        url = f"{pd_base}/store/v1/wallet/{tokens.user_id}"
        async with self._session.get(url, headers=headers) as r:
            if r.status != 200:
                log.error("Wallet erro %s: %s", r.status, await r.text())
                r.raise_for_status()
            data = await r.json(content_type=None)
        balances = data.get("Balances", {})
        return WalletData(
            vp=balances.get(_VP_ID, 0),
            radianite=balances.get(_RAD_ID, 0),
            kingdom_credits=balances.get(_KC_ID, 0),
        )

    async def fetch_rank(self, tokens: RiotTokens, region: str) -> RankData:
        pd_base = self._resolve_pd_url(region)
        headers = self._build_headers(tokens)
        url = f"{pd_base}/mmr/v1/players/{tokens.user_id}"
        async with self._session.get(url, headers=headers) as r:
            if r.status != 200:
                log.error("MMR erro %s: %s", r.status, await r.text())
                r.raise_for_status()
            data = await r.json(content_type=None)

        # Busca dados de tier na API pública
        current = data.get("QueueSkills", {}).get("competitive", {})
        seasonal = current.get("SeasonalInfoBySeasonID", {})

        # Pega a season mais recente
        latest_season = None
        if seasonal:
            latest_season = seasonal[max(seasonal.keys(), key=lambda k: seasonal[k].get("SeasonID", ""))]

        tier = data.get("CurrentTier", 0)
        rr = data.get("CurrentTierProgressTowardsNext", 0)
        leaderboard = data.get("LeaderboardRank", 0)
        wins = latest_season.get("Wins", 0) if latest_season else 0

        # Busca nome e ícone do tier via API pública
        tier_name, tier_icon = await self._fetch_tier_info(tier)
        peak_tier = data.get("HighestSeasonSkill", {}).get("Tier", 0)
        peak_name, peak_icon = await self._fetch_tier_info(peak_tier)

        return RankData(
            tier_name=tier_name,
            tier_icon=tier_icon,
            rr=rr,
            leaderboard_rank=leaderboard,
            wins=wins,
            peak_tier_name=peak_name,
            peak_tier_icon=peak_icon,
        )

    async def fetch_kc_store(self, tokens: RiotTokens, region: str) -> KCStoreData:
        """Busca a loja semanal de Kingdom Credits (AccessoryStore)."""
        pd_base = self._resolve_pd_url(region)
        headers = self._build_headers(tokens)
        storefront = await self._fetch_storefront_v3(pd_base, tokens.user_id, headers)
        return await self._build_kc_store(storefront)

    # ------------------------------------------------------------------ #
    #  Helpers privados                                                    #
    # ------------------------------------------------------------------ #

    def _resolve_pd_url(self, region: str) -> str:
        region = region.lower()
        base = settings.REGIONS.get(region)
        if not base:
            raise ValueError(f"Região '{region}' inválida. Suportadas: {', '.join(settings.REGIONS)}")
        return base

    def _build_headers(self, tokens: RiotTokens) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {tokens.access_token}",
            "X-Riot-Entitlements-JWT": tokens.entitlements_token,
            "X-Riot-ClientPlatform": _CLIENT_PLATFORM,
            "X-Riot-ClientVersion": tokens.client_version,
            "Content-Type": "application/json",
        }

    async def _fetch_storefront_v3(self, pd_base: str, user_id: str, headers: dict) -> dict:
        url = f"{pd_base}/store/v3/storefront/{user_id}"
        async with self._session.post(url, headers=headers, json={}) as r:
            if r.status != 200:
                log.error("Storefront v3 erro %s: %s", r.status, await r.text())
                r.raise_for_status()
            return await r.json(content_type=None)

    async def _fetch_skin_data(self, uuid: str) -> dict:
        url = f"{settings.VAL_API_BASE}/weapons/skinlevels/{uuid}"
        async with self._session.get(url) as r:
            body = await r.json(content_type=None)
        return body.get("data", {})

    async def _fetch_tier_info(self, tier: int) -> tuple[str, str | None]:
        try:
            url = f"{settings.VAL_API_BASE}/competitivetiers"
            async with self._session.get(url) as r:
                data = await r.json(content_type=None)
            tiers = data["data"][-1]["tiers"]  # usa o episódio mais recente
            for t in tiers:
                if t["tier"] == tier:
                    return t.get("tierName", "Unranked"), t.get("largeIcon")
        except Exception as exc:
            log.warning("Falha ao buscar tier info: %s", exc)
        return "Unranked", None

    async def _build_kc_store(self, storefront: dict) -> KCStoreData:
        """Monta as ofertas da loja semanal de Kingdom Credits."""
        accessory = storefront.get("AccessoryStore", {})
        offers_raw = accessory.get("AccessoryStoreOffers", [])
        remaining = accessory.get("AccessoryStoreRemainingDurationInSeconds", 0)

        if not offers_raw:
            return KCStoreData(offers=[], remaining_seconds=remaining)

        async def build_one(item: dict) -> KCOffer:
            offer   = item["Offer"]
            reward  = offer["Rewards"][0]
            item_id = reward["ItemID"]
            type_id = reward.get("ItemTypeID", "")
            item_type = _ITEM_TYPE_NAMES.get(type_id, "Acessório")
            price   = offer.get("Cost", {}).get(_KC_ID, 0)

            # Busca nome e imagem na API pública conforme o tipo
            name, image_url = await self._fetch_accessory_data(item_id, type_id)

            return KCOffer(
                uuid=offer["OfferID"],
                name=name,
                image_url=image_url,
                price=price,
                item_type=item_type,
            )

        offers = list(await asyncio.gather(*[build_one(o) for o in offers_raw]))
        return KCStoreData(offers=offers, remaining_seconds=remaining)

    async def _fetch_accessory_data(self, item_id: str, type_id: str) -> tuple[str, str | None]:
        """Busca nome e imagem de um acessório via valorant-api.com."""
        type_endpoints = {
            "d5f120f8-ff8c-4aac-92ea-f2b5acbe6838": f"sprays/{item_id}",
            "3f296c07-64c3-494c-923b-fe692a4fa1bd": f"playercards/{item_id}",
            "de7caa6b-adf7-4588-aebd-ad8c14603191": f"playertitles/{item_id}",
            "dd3bf334-87f3-40bd-b043-682a57a8dc3a": f"buddies/levels/{item_id}",
        }
        path = type_endpoints.get(type_id)
        if not path:
            return "Acessório desconhecido", None

        try:
            url = f"{settings.VAL_API_BASE}/{path}"
            async with self._session.get(url) as r:
                data = (await r.json(content_type=None)).get("data", {})

            # Cada tipo tem campos ligeiramente diferentes
            name = (
                data.get("displayName")
                or data.get("titleText")
                or "Acessório desconhecido"
            )
            image_url = (
                data.get("displayIcon")
                or data.get("largeArt")
                or data.get("fullTransparentIcon")
                or data.get("killerIcon")
            )
            return name, image_url
        except Exception as exc:
            log.warning("Falha ao buscar acessório %s: %s", item_id, exc)
            return "Acessório desconhecido", None


    async def _build_store_offers(self, storefront: dict) -> list[SkinOffer]:
        vp_id = _VP_ID
        try:
            panel = storefront["SkinsPanelLayout"]
            skin_uuids = panel["SingleItemOffers"]
            offers_data = {o["OfferID"]: o for o in panel.get("SingleItemStoreOffers", [])}
        except KeyError as e:
            log.error("Estrutura inesperada do storefront: %s | keys=%s", e, list(storefront.keys()))
            raise

        async def build_one(uuid: str) -> SkinOffer:
            skin = await self._fetch_skin_data(uuid)
            price = offers_data.get(uuid, {}).get("Cost", {}).get(vp_id, 0)
            return SkinOffer(uuid=uuid, name=skin.get("displayName", "Skin desconhecida"),
                             image_url=skin.get("displayIcon"), price=price)

        return list(await asyncio.gather(*[build_one(u) for u in skin_uuids]))

    async def _build_night_market(self, storefront: dict) -> list[NightMarketOffer]:
        bonus = storefront.get("BonusStore")
        if not bonus:
            return []
        offers_raw = bonus.get("BonusStoreOffers", [])
        if not offers_raw:
            return []

        async def build_one(item: dict) -> NightMarketOffer:
            skin_uuid = item["Offer"]["Rewards"][0]["ItemID"]
            skin = await self._fetch_skin_data(skin_uuid)
            return NightMarketOffer(
                uuid=item["Offer"]["OfferID"],
                name=skin.get("displayName", "Skin desconhecida"),
                image_url=skin.get("displayIcon"),
                original_price=item["Offer"]["Cost"].get(_VP_ID, 0),
                final_price=item["DiscountCosts"].get(_VP_ID, 0),
                discount_percent=item["DiscountPercent"],
            )

        return list(await asyncio.gather(*[build_one(item) for item in offers_raw]))