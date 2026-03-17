import asyncio
import logging

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from services.auth import AuthenticationError, InvalidCookieError, authenticate_with_ssid
from services.store import StoreService
from utils.embeds import (
    build_kc_empty_embed,
    build_kc_offer_embeds,
    build_kc_store_header,
    build_night_market_embeds,
    build_night_market_header,
    build_no_night_market_embed,
    build_rank_embed,
    build_store_embeds,
    build_store_header,
    build_wallet_embed,
)

log = logging.getLogger(__name__)

_VALID_REGIONS = ("na", "eu", "br", "ap", "kr", "latam")
_SSID_TIMEOUT  = 120
_WHERE_TIMEOUT = 30

_REGION_CHOICES = [
    app_commands.Choice(name="Brasil (BR)", value="br"),
    app_commands.Choice(name="Norte América (NA)", value="na"),
    app_commands.Choice(name="Europa (EU)", value="eu"),
    app_commands.Choice(name="Ásia-Pacífico (AP)", value="ap"),
    app_commands.Choice(name="Coreia (KR)", value="kr"),
    app_commands.Choice(name="LATAM", value="latam"),
]

_SSID_GUIDE = """
🔐 **Como autenticar — copie 3 cookies**

**1.** Acesse `https://auth.riotgames.com` e faça login
**2.** Pressione **F12** → aba **Application** (Chrome/Edge) ou **Storage** (Firefox)
**3.** Expanda **Cookies** → clique em `https://auth.riotgames.com`
**4.** Copie o **valor** desses 3 cookies e responda no formato:

```
ssid=VALOR,tdid=VALOR,__Secure-session_state=VALOR
```

💡 **Dica:** O valor do `ssid` pode começar com `eyJ...` — cole assim mesmo, funciona!

> ⚠️ **Aviso de segurança**
> Esses cookies concedem acesso temporário à sua conta Riot.
> Este bot é **open source** e **não armazena** nenhum dado.
> Sua mensagem será **deletada automaticamente**.

📨 **Responda com os cookies no formato acima** *(2 minutos)*:
"""


class WhereView(discord.ui.View):
    """Botões para escolher onde exibir o resultado."""

    def __init__(self, author_id: int, guild_name: str, channel_name: str):
        super().__init__(timeout=_WHERE_TIMEOUT)
        self.choice: str | None = None
        self.author_id = author_id
        self.guild_name = guild_name
        self.channel_name = channel_name

    @discord.ui.button(label="📨 No privado (DM)", style=discord.ButtonStyle.primary)
    async def dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Esse botão não é pra você.", ephemeral=True)
            return
        self.choice = "dm"
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(style=discord.ButtonStyle.secondary)
    async def channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Esse botão não é pra você.", ephemeral=True)
            return
        self.choice = "channel"
        self.stop()
        await interaction.response.defer()

    def set_channel_label(self) -> None:
        """Atualiza o label do botão canal com o nome real do servidor/canal."""
        self.channel.label = f"📢 #{self.channel_name} ({self.guild_name})"


class StoreCog(commands.Cog, name="Loja"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ================================================================== #
    #  SLASH COMMANDS                                                      #
    # ================================================================== #

    @app_commands.command(name="store", description="Mostra sua loja diária do Valorant 🛒")
    @app_commands.describe(region="Sua região no Valorant")
    @app_commands.choices(region=_REGION_CHOICES)
    async def slash_store(self, interaction: discord.Interaction, region: str = "br") -> None:
        await self._slash_flow(interaction, region, mode="store")

    @app_commands.command(name="nightmarket", description="Mostra seu mercado noturno do Valorant 🌙")
    @app_commands.describe(region="Sua região no Valorant")
    @app_commands.choices(region=_REGION_CHOICES)
    async def slash_nightmarket(self, interaction: discord.Interaction, region: str = "br") -> None:
        await self._slash_flow(interaction, region, mode="nightmarket")

    @app_commands.command(name="wallet", description="Mostra seu saldo de VP, Radianite e Kingdom Credits 💰")
    @app_commands.describe(region="Sua região no Valorant")
    @app_commands.choices(region=_REGION_CHOICES)
    async def slash_wallet(self, interaction: discord.Interaction, region: str = "br") -> None:
        await self._slash_flow(interaction, region, mode="wallet")

    @app_commands.command(name="rank", description="Mostra seu rank competitivo atual 🏆")
    @app_commands.describe(region="Sua região no Valorant")
    @app_commands.choices(region=_REGION_CHOICES)
    async def slash_rank(self, interaction: discord.Interaction, region: str = "br") -> None:
        await self._slash_flow(interaction, region, mode="rank")

    @app_commands.command(name="kcstore", description="Mostra a loja semanal de Kingdom Credits 👑")
    @app_commands.describe(region="Sua região no Valorant")
    @app_commands.choices(region=_REGION_CHOICES)
    async def slash_kcstore(self, interaction: discord.Interaction, region: str = "br") -> None:
        await self._slash_flow(interaction, region, mode="kcstore")

    # ================================================================== #
    #  PREFIX COMMANDS (mantidos para compatibilidade)                     #
    # ================================================================== #

    @commands.command(name="store", aliases=["loja"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def prefix_store(self, ctx: commands.Context, region: str = "br") -> None:
        """Mostra sua loja diária. Uso: !store [região]"""
        await self._prefix_flow(ctx, region.lower(), mode="store")

    @commands.command(name="nightmarket", aliases=["nm", "mercadonoturno"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def prefix_nightmarket(self, ctx: commands.Context, region: str = "br") -> None:
        """Mostra seu mercado noturno. Uso: !nightmarket [região]"""
        await self._prefix_flow(ctx, region.lower(), mode="nightmarket")

    @commands.command(name="wallet", aliases=["carteira", "vp"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def prefix_wallet(self, ctx: commands.Context, region: str = "br") -> None:
        """Mostra seu saldo. Uso: !wallet [região]"""
        await self._prefix_flow(ctx, region.lower(), mode="wallet")

    @commands.command(name="rank", aliases=["mmr", "elo"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def prefix_rank(self, ctx: commands.Context, region: str = "br") -> None:
        """Mostra seu rank. Uso: !rank [região]"""
        await self._prefix_flow(ctx, region.lower(), mode="rank")

    @commands.command(name="kcstore", aliases=["kc", "accessories"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def prefix_kcstore(self, ctx: commands.Context, region: str = "br") -> None:
        """Mostra a loja de Kingdom Credits. Uso: !kcstore [região]"""
        await self._prefix_flow(ctx, region.lower(), mode="kcstore")

    @prefix_store.error
    @prefix_nightmarket.error
    @prefix_wallet.error
    @prefix_rank.error
    @prefix_kcstore.error
    async def _on_cooldown(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Aguarde **{error.retry_after:.0f}s** para usar esse comando novamente.")

    # ================================================================== #
    #  Fluxo slash                                                         #
    # ================================================================== #

    async def _slash_flow(self, interaction: discord.Interaction, region: str, mode: str) -> None:
        """Fluxo para slash commands — usa ephemeral + DM."""
        # Responde imediatamente para não deixar o Discord expirar a interação
        await interaction.response.send_message(
            "📨 Enviei as instruções no seu privado! Responda por lá.",
            ephemeral=True,
        )

        user = interaction.user
        ssid = await self._request_ssid_dm(user)
        if not ssid:
            await interaction.followup.send("⏰ Tempo esgotado.", ephemeral=True)
            return

        # Pergunta onde exibir (só em servidor)
        destination = "dm"
        if interaction.guild:
            destination = await self._ask_destination_slash(interaction, user)
            if destination is None:
                return

        await self._execute(user, interaction.channel, ssid, region, mode, destination)

    # ================================================================== #
    #  Fluxo prefix                                                        #
    # ================================================================== #

    async def _prefix_flow(self, ctx: commands.Context, region: str, mode: str) -> None:
        if region not in _VALID_REGIONS:
            await ctx.send(f"❌ Região inválida. Use: `{'`, `'.join(_VALID_REGIONS)}`")
            return

        ssid = await self._request_ssid(ctx)
        if not ssid:
            return

        destination = "dm"
        if ctx.guild:
            destination = await self._ask_destination(ctx)
            if destination is None:
                await ctx.send("⏰ Tempo esgotado.")
                return

        await self._execute(ctx.author, ctx.channel, ssid, region, mode, destination)

    # ================================================================== #
    #  Core — autenticar, buscar e enviar                                  #
    # ================================================================== #

    async def _execute(
        self,
        user: discord.User,
        channel,
        ssid: str,
        region: str,
        mode: str,
        destination: str,
    ) -> None:
        loading = await user.send("⏳ Autenticando e buscando dados...")

        async with aiohttp.ClientSession() as session:
            try:
                tokens = await authenticate_with_ssid(ssid, session, discord_name=str(user))
                del ssid

                service = StoreService(session)
                if mode in ("store", "nightmarket"):
                    data = await service.fetch_store(tokens, region)
                elif mode == "wallet":
                    data = await service.fetch_wallet(tokens, region)
                elif mode == "rank":
                    data = await service.fetch_rank(tokens, region)
                elif mode == "kcstore":
                    data = await service.fetch_kc_store(tokens, region)

            except InvalidCookieError:
                await loading.edit(content="❌ **ssid inválido ou expirado.** Obtenha um novo e tente novamente.")
                return
            except AuthenticationError as exc:
                log.warning("Falha de auth para %s: %s", user, exc)
                await loading.edit(content=f"❌ Erro de autenticação: {exc}")
                return
            except Exception as exc:
                log.error("Erro inesperado: %s", exc, exc_info=True)
                await loading.edit(content="❌ Erro inesperado. Tente novamente mais tarde.")
                return

        await loading.delete()

        target = channel if destination == "channel" else user

        dn = tokens.discord_name
        if mode == "store":
            await self._send_store(target, data, tokens)
        elif mode == "nightmarket":
            await self._send_night_market(target, data, tokens)
        elif mode == "wallet":
            await target.send(embed=build_wallet_embed(data, tokens.game_name, tokens.tag_line, dn))
        elif mode == "rank":
            await target.send(embed=build_rank_embed(data, tokens.game_name, tokens.tag_line, dn))
        elif mode == "kcstore":
            await self._send_kc_store(target, data, tokens)

    # ================================================================== #
    #  Coleta do ssid                                                      #
    # ================================================================== #

    async def _request_ssid_dm(self, user: discord.User) -> str | None:
        """Envia guia e aguarda ssid — usado pelos slash commands."""
        try:
            await user.send(_SSID_GUIDE)
        except discord.Forbidden:
            return None

        def is_reply(m: discord.Message) -> bool:
            return (
                m.author.id == user.id
                and isinstance(m.channel, discord.DMChannel)
                and len(m.content.strip()) > 10
            )

        try:
            msg = await self.bot.wait_for("message", check=is_reply, timeout=_SSID_TIMEOUT)
        except asyncio.TimeoutError:
            await user.send("⏰ Tempo esgotado.")
            return None

        ssid = msg.content.strip()
        try:
            await msg.delete()
        except discord.HTTPException:
            pass
        return ssid

    async def _request_ssid(self, ctx: commands.Context) -> str | None:
        """Envia guia e aguarda ssid — usado pelos prefix commands."""
        try:
            await ctx.author.send(_SSID_GUIDE)
        except discord.Forbidden:
            await ctx.send(
                f"❌ {ctx.author.mention} Não consigo te enviar DM.\n"
                "Habilite **Mensagens Diretas** neste servidor e tente novamente."
            )
            return None

        if ctx.guild:
            await ctx.send(f"📨 {ctx.author.mention} Enviei as instruções no privado!")

        return await self._request_ssid_dm(ctx.author)

    # ================================================================== #
    #  Escolha de destino                                                  #
    # ================================================================== #

    async def _ask_destination(self, ctx: commands.Context) -> str | None:
        guild_name   = ctx.guild.name if ctx.guild else "DM"
        channel_name = ctx.channel.name if hasattr(ctx.channel, "name") else "canal"
        view = WhereView(ctx.author.id, guild_name, channel_name)
        view.set_channel_label()
        prompt = await ctx.send(
            f"📍 {ctx.author.mention} Onde você quer ver o resultado?",
            view=view,
        )
        await view.wait()
        try:
            await prompt.delete()
        except discord.HTTPException:
            pass
        return view.choice

    async def _ask_destination_slash(
        self, interaction: discord.Interaction, user: discord.User
    ) -> str | None:
        guild_name   = interaction.guild.name if interaction.guild else "DM"
        channel_name = interaction.channel.name if hasattr(interaction.channel, "name") else "canal"
        view = WhereView(user.id, guild_name, channel_name)
        view.set_channel_label()
        msg = await user.send("📍 Onde você quer ver o resultado?", view=view)
        await view.wait()
        try:
            await msg.delete()
        except discord.HTTPException:
            pass
        return view.choice

    # ================================================================== #
    #  Envio dos resultados                                                #
    # ================================================================== #

    async def _send_store(self, target, store, tokens) -> None:
        dn = tokens.discord_name
        await target.send(embed=build_store_header(tokens.game_name, tokens.tag_line, dn))
        for embed in build_store_embeds(store, tokens.game_name, tokens.tag_line, dn):
            await target.send(embed=embed)

    async def _send_night_market(self, target, store, tokens) -> None:
        dn = tokens.discord_name
        if store.has_night_market:
            await target.send(embed=build_night_market_header(tokens.game_name, tokens.tag_line, dn))
            for embed in build_night_market_embeds(store.night_market, tokens.game_name, tokens.tag_line, dn):
                await target.send(embed=embed)
        else:
            await target.send(embed=build_no_night_market_embed())

    async def _send_kc_store(self, target, kc_store, tokens) -> None:
        dn = tokens.discord_name
        if not kc_store.offers:
            await target.send(embed=build_kc_empty_embed())
            return
        await target.send(embed=build_kc_store_header(tokens.game_name, tokens.tag_line, kc_store.remaining_hours, dn))
        for embed in build_kc_offer_embeds(kc_store, tokens.game_name, tokens.tag_line, dn):
            await target.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StoreCog(bot))