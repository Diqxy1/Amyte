"""
Construtores de embeds Discord para loja, mercado noturno, wallet e rank.
"""

import discord

from services.store import KCOffer, KCStoreData, NightMarketOffer, RankData, SkinOffer, StoreData, WalletData

def _display_name(game_name: str, tag_line: str, discord_name: str = "") -> str:
    """
    Retorna o melhor nome disponível na ordem:
    1. Nome Valorant (game_name#tag)
    2. Nick do Discord
    3. 'Agente' como último fallback
    """
    if game_name and game_name != "Agente":
        return f"{game_name}#{tag_line}" if tag_line else game_name
    if discord_name:
        return discord_name
    return "Agente"


_STORE_COLORS = [
    discord.Color.from_rgb(255, 70, 85),
    discord.Color.from_rgb(255, 143, 0),
    discord.Color.from_rgb(0, 212, 170),
    discord.Color.from_rgb(189, 147, 249),
]
_NM_COLOR  = discord.Color.from_rgb(20, 20, 50)
_VAL_RED   = discord.Color.from_rgb(255, 70, 85)


def _vp(amount: int) -> str:
    return f"**{amount:,} VP**"


# ------------------------------------------------------------------ #
#  Loja diária                                                         #
# ------------------------------------------------------------------ #

def build_store_header(game_name: str, tag: str, discord_name: str = "") -> discord.Embed:
    name = _display_name(game_name, tag, discord_name)
    return discord.Embed(
        description=f"🛒 Loja de **{name}**\nRenovada diariamente às **00:00 UTC**.",
        color=_VAL_RED,
    )


def build_store_embeds(store: StoreData, game_name: str, tag: str = "", discord_name: str = "") -> list[discord.Embed]:
    name = _display_name(game_name, tag, discord_name)
    embeds = []
    for i, skin in enumerate(store.skins):
        embed = discord.Embed(title=skin.name, color=_STORE_COLORS[i % len(_STORE_COLORS)])
        embed.set_author(name=f"🏪 Loja de {name}")
        embed.add_field(name="💰 Preço", value=_vp(skin.price), inline=True)
        embed.add_field(name="🎯 Item",  value=f"`{i + 1} / 4`",  inline=True)
        if skin.image_url:
            embed.set_image(url=skin.image_url)
        embed.set_footer(text="Amyte")
        embeds.append(embed)
    return embeds


# ------------------------------------------------------------------ #
#  Mercado noturno                                                     #
# ------------------------------------------------------------------ #

def build_night_market_header(game_name: str, tag: str, discord_name: str = "") -> discord.Embed:
    name = _display_name(game_name, tag, discord_name)
    return discord.Embed(
        title="🌙 Mercado Noturno",
        description=f"Ofertas exclusivas para **{name}** 🏷️",
        color=_NM_COLOR,
    )


def build_night_market_embeds(offers: list[NightMarketOffer], game_name: str, tag: str = "", discord_name: str = "") -> list[discord.Embed]:
    name = _display_name(game_name, tag, discord_name)
    embeds = []
    total = len(offers)
    for i, offer in enumerate(offers):
        embed = discord.Embed(title=offer.name, color=_NM_COLOR)
        embed.set_author(name=f"🌙 Mercado Noturno de {name}")
        embed.add_field(name="💸 Original",     value=f"~~{_vp(offer.original_price)}~~", inline=True)
        embed.add_field(name="🏷️ Com desconto", value=_vp(offer.final_price),             inline=True)
        embed.add_field(name="📉 Desconto",     value=f"**{offer.discount_percent}% OFF**", inline=True)
        embed.add_field(name="🎯 Item",         value=f"`{i + 1} / {total}`",              inline=True)
        if offer.image_url:
            embed.set_image(url=offer.image_url)
        embed.set_footer(text="Amyte")
        embeds.append(embed)
    return embeds


def build_no_night_market_embed() -> discord.Embed:
    return discord.Embed(
        title="🌙 Mercado Noturno",
        description="O Mercado Noturno **não está disponível** no momento.\nFique de olho nas novidades da Riot!",
        color=discord.Color.dark_grey(),
    )


# ------------------------------------------------------------------ #
#  Wallet                                                              #
# ------------------------------------------------------------------ #

def build_wallet_embed(wallet: WalletData, game_name: str, tag: str = "", discord_name: str = "") -> discord.Embed:
    name = _display_name(game_name, tag, discord_name)
    embed = discord.Embed(
        title="💰 Carteira",
        description=f"Saldo de **{name}**",
        color=discord.Color.from_rgb(255, 200, 0),
    )
    embed.add_field(name="<:vp:1> Valorant Points", value=f"**{wallet.vp:,}**",             inline=True)
    embed.add_field(name="✨ Radianite Points",      value=f"**{wallet.radianite:,}**",       inline=True)
    embed.add_field(name="👑 Kingdom Credits",       value=f"**{wallet.kingdom_credits:,}**", inline=True)
    embed.set_footer(text="Amyte")
    return embed


# ------------------------------------------------------------------ #
#  Rank                                                                #
# ------------------------------------------------------------------ #

def build_rank_embed(rank: RankData, game_name: str, tag: str = "", discord_name: str = "") -> discord.Embed:
    name = _display_name(game_name, tag, discord_name)
    embed = discord.Embed(
        title=f"🏆 Rank de {name}",
        color=discord.Color.from_rgb(255, 200, 80),
    )
    embed.add_field(name="📊 Rank Atual",  value=f"**{rank.tier_name}**\n{rank.rr} RR", inline=True)
    embed.add_field(name="🏅 Pico",        value=f"**{rank.peak_tier_name}**",           inline=True)

    if rank.leaderboard_rank > 0:
        embed.add_field(name="🏟️ Leaderboard", value=f"**#{rank.leaderboard_rank}**",   inline=True)

    embed.add_field(name="✅ Vitórias",    value=f"**{rank.wins}**",                     inline=True)

    if rank.tier_icon:
        embed.set_thumbnail(url=rank.tier_icon)

    embed.set_footer(text="Amyte")
    return embed


# ------------------------------------------------------------------ #
#  Loja de Kingdom Credits                                             #
# ------------------------------------------------------------------ #

_KC_COLOR = discord.Color.from_rgb(255, 215, 0)  # Dourado

_ITEM_TYPE_EMOJI = {
    "Spray":        "💨",
    "Player Card":  "🃏",
    "Player Title": "📛",
    "Gun Buddy":    "🧸",
    "Acessório":    "🎁",
}


def build_kc_store_header(game_name: str, tag: str, remaining_hours: int, discord_name: str = "") -> discord.Embed:
    player_name = _display_name(game_name, tag, discord_name)
    days  = remaining_hours // 24
    hours = remaining_hours % 24
    time_str = f"{days}d {hours}h" if days else f"{hours}h"
    return discord.Embed(
        title="👑 Loja de Kingdom Credits",
        description=(
            f"Ofertas semanais de **{player_name}#{tag}** "
            + (f"({discord_name})" if discord_name and not (player_name and tag) else "")
            + f"\n⏳ Renova em **{time_str}**"
        ),
        color=_KC_COLOR,
    )


def build_kc_offer_embeds(kc_store: KCStoreData, game_name: str, tag: str = "", discord_name: str = "") -> list[discord.Embed]:
    player_name = _display_name(game_name, tag, discord_name)
    embeds = []
    total = len(kc_store.offers)
    for i, offer in enumerate(kc_store.offers):
        emoji = _ITEM_TYPE_EMOJI.get(offer.item_type, "🎁")
        embed = discord.Embed(
            title=offer.name,
            color=_KC_COLOR,
        )
        embed.set_author(name=f"👑 KC Store de {player_name}")
        embed.add_field(name=f"{emoji} Tipo",     value=offer.item_type,        inline=True)
        embed.add_field(name="👑 Preço KC",        value=f"**{offer.price:,} KC**", inline=True)
        embed.add_field(name="🎯 Item",            value=f"`{i + 1} / {total}`", inline=True)
        if offer.image_url:
            embed.set_thumbnail(url=offer.image_url)
        embed.set_footer(text="Amyte • Loja semanal de Kingdom Credits")
        embeds.append(embed)
    return embeds


def build_kc_empty_embed() -> discord.Embed:
    return discord.Embed(
        title="👑 Loja de Kingdom Credits",
        description="Nenhuma oferta disponível no momento.",
        color=discord.Color.dark_grey(),
    )