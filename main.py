import asyncio
import logging
import sys

import discord
from discord.ext import commands

from config import settings
from utils.logger import setup_logger

setup_logger()
log = logging.getLogger(__name__)


def create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = commands.Bot(
        command_prefix=settings.PREFIX,
        intents=intents,
        help_command=None,
        description="Amyte — veja sua loja e mercado noturno.",
    )
    return bot


bot = create_bot()


async def load_cogs() -> None:
    cogs = ["cogs.general", "cogs.store"]
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            log.info(f"Cog carregada: {cog}")
        except Exception as e:
            log.error(f"Falha ao carregar cog {cog}: {e}", exc_info=True)


@bot.event
async def on_ready() -> None:
    log.info(f"Bot online como {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="sua lojinha 💜 | /store",
        )
    )
    # Sincroniza slash commands globalmente
    try:
        synced = await bot.tree.sync()
        log.info(f"Slash commands sincronizados: {len(synced)} comandos")
    except Exception as e:
        log.error(f"Falha ao sincronizar slash commands: {e}")


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão para usar esse comando.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argumento faltando: `{error.param.name}`")
        return
    log.error(f"Erro no comando '{ctx.command}': {error}", exc_info=True)
    await ctx.send("❌ Ocorreu um erro inesperado. Tente novamente mais tarde.")


async def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    async with bot:
        await load_cogs()
        await bot.start(settings.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())