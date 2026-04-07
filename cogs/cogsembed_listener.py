from discord.ext import commands
import re
import json
import os
import random
import discord
import asyncio

SOURCE_CHANNEL = 1315771552742117447
REQUIRED_WORDS = ["latte", "napoli"]

MAGAZZINO_FILE = "magazzino.json"
CONFIG_FILE = "magazzino_config.json"


def load_magazzino():
    if not os.path.exists(MAGAZZINO_FILE):
        return {}
    with open(MAGAZZINO_FILE, "r") as f:
        return json.load(f)


def save_magazzino(data):
    with open(MAGAZZINO_FILE, "w") as f:
        json.dump(data, f, indent=4)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"channel_id": None, "message_id": None}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


async def update_magazzino_embed(bot):
    """Aggiorna l'embed del magazzino con barre verdi/bianche e quantità"""
    data = load_magazzino()
    config = load_config()
    channel = bot.get_channel(config["channel_id"])
    if not channel:
        return
    try:
        msg = await channel.fetch_message(config["message_id"])
    except:
        return

    embed = discord.Embed(title="📦 Magazzino", color=discord.Color.blue())
    for p, info in data.items():
        quantita = info["quantita"]
        massimo = info["massimo"] if info["massimo"] > 0 else 1
        percent = quantita / massimo
        verdi = round(percent * 10)
        bianchi = 10 - verdi
        barra = "🟩" * verdi + "⬜" * bianchi
        embed.add_field(name=p, value=f"{barra} {quantita}/{massimo}", inline=False)

    await msg.edit(embed=embed)


async def produzione(bot, channel, prodotto):
    """Produzione con barra verde/bianca e countdown di 60 secondi"""
    # Messaggio iniziale
    msg_embed = await channel.send(embed=discord.Embed(
        title=f"🏭 Produzione avviata: {prodotto}",
        description="⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜\n⏳ Tempo rimanente: 60 secondi",
        color=discord.Color.green()
    ))

    for i in range(1, 11):
        await asyncio.sleep(6)  # 10 step * 6 secondi = 60 secondi totale
        verdi = i
        bianchi = 10 - i
        barra = "🟩" * verdi + "⬜" * bianchi
        try:
            await msg_embed.edit(embed=discord.Embed(
                title=f"🏭 Produzione in corso: {prodotto}",
                description=f"{barra}\n⏳ Tempo rimanente: {60 - i*6} secondi",
                color=discord.Color.green()
            ))
        except:
            return

    # Aggiorna il magazzino finale
    data = load_magazzino()
    if data[prodotto]["quantita"] < data[prodotto]["massimo"]:
        data[prodotto]["quantita"] += 1
    save_magazzino(data)

    await update_magazzino_embed(bot)

    # Messaggio finale produzione completata
    await msg_embed.edit(embed=discord.Embed(
        title=f"✅ Produzione completata: {prodotto}",
        color=discord.Color.green()
    ))

    await asyncio.sleep(3)
    try:
        await msg_embed.delete()
    except:
        pass


class ProdottoSelect(discord.ui.Select):
    def __init__(self, prodotti, view):
        options = [discord.SelectOption(label=p) for p in prodotti]
        super().__init__(placeholder="Scegli prodotto da produrre", options=options)
        self.custom_view = view

    async def callback(self, interaction: discord.Interaction):
        prodotto = self.values[0]
        self.custom_view.stop()
        try:
            await interaction.message.delete()
        except:
            pass
        await interaction.response.defer()
        await produzione(interaction.client, interaction.channel, prodotto)


class ProdottoView(discord.ui.View):
    def __init__(self, prodotti, bot):
        super().__init__(timeout=60)  # timeout 60 secondi invece di 10
        self.bot = bot
        self.prodotti = prodotti
        self.add_item(ProdottoSelect(prodotti, self))

    async def auto_produce(self, message):
        data = load_magazzino()
        disponibili = [p for p, info in data.items() if info["quantita"] < info["massimo"]]
        if not disponibili:
            try:
                await message.delete()
            except:
                pass
            return
        prodotto = random.choice(disponibili)
        try:
            await message.delete()
        except:
            pass
        await produzione(self.bot, message.channel, prodotto)


class EmbedListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.id != SOURCE_CHANNEL or not message.embeds:
            return

        for embed in message.embeds:
            text_parts = []
            if embed.title:
                text_parts.append(embed.title)
            if embed.description:
                text_parts.append(embed.description)
            if embed.footer and embed.footer.text:
                text_parts.append(embed.footer.text)
            if embed.author and embed.author.name:
                text_parts.append(embed.author.name)
            for field in embed.fields:
                text_parts.append(field.name)
                text_parts.append(field.value)

            text = " ".join(text_parts).lower()
            words = re.findall(r"\w+", text)

            if all(word in words for word in REQUIRED_WORDS):
                data = load_magazzino()
                if not data:
                    return
                config = load_config()
                channel = self.bot.get_channel(config["channel_id"])
                if not channel:
                    return
                prodotti = list(data.keys())
                view = ProdottoView(prodotti, self.bot)
                msg = await channel.send(
                    "🚚 **Una consegna di latte è arrivata.**\n"
                    "Quale prodotto bisogna produrre?\n\n"
                    "⏳ Tempo prima che una produzione venga avviata automaticamente: **60 secondi**",
                    view=view
                )

                for i in range(59, -1, -1):
                    await asyncio.sleep(1)
                    if view.is_finished():
                        return
                    try:
                        await msg.edit(
                            content=(
                                "🚚 **Una consegna di latte è arrivata.**\n"
                                "Quale prodotto bisogna produrre?\n\n"
                                f"⏳ Tempo prima che una produzione venga avviata automaticamente: **{i} secondi**"
                            ),
                            view=view
                        )
                    except:
                        return

                if not view.is_finished():
                    await view.auto_produce(msg)


async def setup(bot):
    await bot.add_cog(EmbedListener(bot))