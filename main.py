import discord
from discord.ext import commands
import asyncio

import config
from core.loader import load_cogs

# Controllo sicurezza
if not config.TOKEN:
    raise ValueError("TOKEN mancante! Controlla le variabili Railway.")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=config.PREFIX,
    intents=intents
)

@bot.event
async def on_ready():
    print(f"✅ Bot online: {bot.user} (ID: {bot.user.id})")

async def main():
    async with bot:
        await load_cogs(bot)
        await bot.start(config.TOKEN)

asyncio.run(main())