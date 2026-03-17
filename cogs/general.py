import logging

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)


class GeneralCog(commands.Cog, name="Geral"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ================================================================== #
    #  SLASH COMMANDS                                                      #
    # ================================================================== #

    @app_commands.command(name="help", description="Mostra todos os comandos disponíveis 📖")
    async def slash_help(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=self._build_help_embed(), ephemeral=True)

    @app_commands.command(name="ping", description="Verifica a latência do bot 🏓")
    async def slash_ping(self, interaction: discord.Interaction) -> None:
        ms = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            embed=self._build_ping_embed(ms), ephemeral=True
        )

    # ================================================================== #
    #  PREFIX COMMANDS                                                     #
    # ================================================================== #

    @commands.command(name="ping")
    async def prefix_ping(self, ctx: commands.Context) -> None:
        """Exibe a latência do bot."""
        ms = round(self.bot.latency * 1000)
        await ctx.send(embed=self._build_ping_embed(ms))

    @commands.command(name="help", aliases=["ajuda"])
    async def prefix_help(self, ctx: commands.Context) -> None:
        """Exibe a lista de comandos disponíveis."""
        await ctx.send(embed=self._build_help_embed())

    @commands.command(name="clear", aliases=["limpar"])
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx: commands.Context, amount: int = 10) -> None:
        """Apaga mensagens do canal. Requer permissão manage_messages."""
        if not 1 <= amount <= 100:
            await ctx.send("❌ Informe um número entre 1 e 100.")
            return
        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"🗑️ {len(deleted) - 1} mensagens apagadas.", delete_after=5)

    # ================================================================== #
    #  Helpers                                                             #
    # ================================================================== #

    def _build_ping_embed(self, ms: int) -> discord.Embed:
        color = (
            discord.Color.green()  if ms < 100 else
            discord.Color.yellow() if ms < 200 else
            discord.Color.red()
        )
        return discord.Embed(title="🏓 Pong!", description=f"Latência: **{ms}ms**", color=color)

    def _build_help_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📖 Comandos disponíveis",
            description="Bot para visualizar sua loja do Valorant.\nUse `/comando` ou `!comando`.",
            color=discord.Color.from_rgb(255, 70, 85),
        )
        embed.add_field(
            name="🏪 Loja",
            value=(
                "`/store` ou `!store` — Loja diária\n"
                "`/nightmarket` ou `!nightmarket` — Mercado noturno\n"
                "`/wallet` ou `!wallet` — Saldo de VP, Radianite e KC\n"
                "`/rank` ou `!rank` — Rank competitivo\n"
                "`/kcstore` ou `!kcstore` — Loja semanal de Kingdom Credits\n\n"
                "**Regiões:** `br` · `na` · `eu` · `ap` · `kr` · `latam`"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚙️ Geral",
            value="`/ping` ou `!ping` — Latência\n`/help` ou `!help` — Esta mensagem",
            inline=False,
        )
        embed.add_field(
            name="🔐 Segurança",
            value=(
                "Autenticação via **cookie ssid** — sem senha.\n"
                "Código **open source**, nenhum dado é armazenado.\n"
                "Resultados podem ser enviados via **DM** ou no **canal**."
            ),
            inline=False,
        )
        embed.set_footer(text="Amyte • open source • github.com/Diqxy1/Amyte")
        return embed

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        log.info("Bot adicionado: %s (ID: %s)", guild.name, guild.id)
        channel = next(
            (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages),
            None,
        )
        if channel:
            embed = discord.Embed(
                title="👋 Olá! Sou a Amyte",
                description=(
                    "Use `/help` para ver todos os comandos.\n\n"
                    "Comece com `/store` para ver sua loja diária! 🛒"
                ),
                color=discord.Color.from_rgb(255, 70, 85),
            )
            await channel.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GeneralCog(bot))