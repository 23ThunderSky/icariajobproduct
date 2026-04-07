from discord.ext import commands, tasks
import discord
import json
import os
import random
import asyncio

PORTO_FILE = "porto.json"
CONFIG_FILE = "porto_config.json"
CLIENTI_PORTO_FILE = "clientiporto.json"

ALLOWED_ROLES = [1315767688437436476, 1166815641790070794]

# ------------------- FILE -------------------
def load_porto():
    if not os.path.exists(PORTO_FILE):
        return {}
    with open(PORTO_FILE) as f:
        return json.load(f)

def save_porto(data):
    with open(PORTO_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_clienti_porto():
    if not os.path.exists(CLIENTI_PORTO_FILE):
        return {}
    with open(CLIENTI_PORTO_FILE) as f:
        return json.load(f)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"channel_id": None, "message_id": None}
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ------------------- EMBED -------------------
def create_embed(data):
    embed = discord.Embed(title="🚢 Porto", color=discord.Color.dark_teal())
    if not data:
        embed.description = "Nessun carico"
    else:
        for nome, info in data.items():
            quantita = info.get("quantita", 0)
            massimo = info.get("massimo", 1)
            percent = quantita / massimo if massimo > 0 else 0
            verdi = round(percent * 10)
            bianchi = 10 - verdi
            barra = "🟩" * verdi + "⬜" * bianchi
            embed.add_field(
                name=nome,
                value=f"{barra} {quantita}/{massimo}",
                inline=False
            )
    return embed

async def update_porto_embed(bot):
    config = load_config()
    channel = bot.get_channel(config["channel_id"])
    if not channel:
        return
    try:
        msg = await channel.fetch_message(config["message_id"])
    except:
        return
    await msg.edit(embed=create_embed(load_porto()), view=PortoView())

# ------------------- LOOP MERCE -------------------
class Porto(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_add.start()

    def cog_unload(self):
        self.auto_add.cancel()

    @tasks.loop(hours=1)  # ogni 1 ora
    async def auto_add(self):
        data = load_porto()
        if not data:
            return

        disponibili = [k for k, v in data.items() if v["quantita"] < v["massimo"]]
        if not disponibili:
            return

        scelta = random.choice(disponibili)
        prodotto, porto_nome = scelta.split(" (")
        porto_nome = porto_nome.rstrip(")")
        channel = self.bot.get_channel(load_config()["channel_id"])
        if not channel:
            return

        # --- Countdown prima dell'arrivo della nave (1h), aggiornamento ogni secondo ---
        total_seconds = 3600  # 1 ora
        countdown_msg = await channel.send(
            f"⏳ Prossima nave in arrivo a **{porto_nome}** con **{prodotto}**: 01:00:00"
        )

        for remaining in range(total_seconds, 0, -1):
            ore = remaining // 3600
            minuti = (remaining % 3600) // 60
            secondi = remaining % 60
            try:
                await countdown_msg.edit(
                    content=f"⏳ Prossima nave in arrivo a **{porto_nome}** con **{prodotto}**: {ore:02d}:{minuti:02d}:{secondi:02d}"
                )
            except discord.NotFound:
                break
            await asyncio.sleep(1)

        # --- Alla fine del countdown, aumenta +1 e aggiorna embed ---
        data = load_porto()
        if scelta in data and data[scelta]["quantita"] < data[scelta]["massimo"]:
            data[scelta]["quantita"] += 1
            save_porto(data)
            await update_porto_embed(self.bot)

            await countdown_msg.delete()

            # Messaggio nave arrivata con countdown visibile 30 minuti
            ship_seconds = 1800
            ship_msg = await channel.send(
                f"🚢 Una nave è arrivata al porto di **{porto_nome}** e ha portato 1 **{prodotto}**! Tempo rimanente prima che sparisca: 00:30:00"
            )

            for remaining in range(ship_seconds, 0, -1):
                ore = remaining // 3600
                minuti = (remaining % 3600) // 60
                secondi = remaining % 60
                try:
                    await ship_msg.edit(
                        content=f"🚢 Una nave è arrivata al porto di **{porto_nome}** e ha portato 1 **{prodotto}**! Tempo rimanente prima che sparisca: {ore:02d}:{minuti:02d}:{secondi:02d}"
                    )
                except discord.NotFound:
                    break
                await asyncio.sleep(1)
            try:
                await ship_msg.delete()
            except discord.NotFound:
                pass
        else:
            await countdown_msg.delete()

    @commands.command()
    async def porto(self, ctx):
        msg = await ctx.send(embed=create_embed(load_porto()), view=PortoView())
        config = load_config()
        config["channel_id"] = ctx.channel.id
        config["message_id"] = msg.id
        save_config(config)

# ------------------- SELECT -------------------
class AddFromClientiSelect(discord.ui.Select):
    def __init__(self, clienti):
        options = [
            discord.SelectOption(label=c, description=clienti[c]["carico"])
            for c in clienti
        ]
        super().__init__(placeholder="Scegli cliente/carico", options=options)
        self.clienti = clienti

    async def callback(self, interaction: discord.Interaction):
        cliente = self.values[0]
        carico = self.clienti[cliente]["carico"]
        porto_nome = self.clienti[cliente]["porto"]
        key = f"{carico} ({porto_nome})"

        data = load_porto()
        if key not in data:
            data[key] = {"quantita": 0, "massimo": self.clienti[cliente]["camion"]}
        else:
            data[key]["quantita"] = data[key].get("quantita", 0)

        save_porto(data)
        await update_porto_embed(interaction.client)
        await interaction.response.send_message(f"✅ Creato carico **{key}**", ephemeral=True)

class AddView(discord.ui.View):
    def __init__(self, clienti):
        super().__init__(timeout=60)
        self.add_item(AddFromClientiSelect(clienti))

# ------------------- REMOVE -------------------
class RemoveSelect(discord.ui.Select):
    def __init__(self, prodotti):
        super().__init__(
            placeholder="Scegli carico da rimuovere",
            options=[discord.SelectOption(label=p) for p in prodotti]
        )

    async def callback(self, interaction: discord.Interaction):
        data = load_porto()
        prodotto = self.values[0]
        if prodotto in data:
            del data[prodotto]
            save_porto(data)

        await update_porto_embed(interaction.client)
        await interaction.response.send_message(f"❌ Carico **{prodotto}** rimosso", ephemeral=True)

class RemoveView(discord.ui.View):
    def __init__(self, prodotti):
        super().__init__(timeout=60)
        self.add_item(RemoveSelect(prodotti))

# ------------------- VIEW -------------------
class PortoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def check(self, interaction):
        return any(role.id in ALLOWED_ROLES for role in interaction.user.roles)

    @discord.ui.button(label="➕ Aggiungi prodotto", style=discord.ButtonStyle.success)
    async def add(self, interaction, button):
        if not self.check(interaction):
            return await interaction.response.send_message("No permessi", ephemeral=True)

        clienti = load_clienti_porto()
        if not clienti:
            return await interaction.response.send_message("Nessun cliente porto disponibile", ephemeral=True)

        await interaction.response.send_message("Seleziona cliente/carico:", view=AddView(clienti), ephemeral=True)

    @discord.ui.button(label="➖ Rimuovi prodotto", style=discord.ButtonStyle.danger)
    async def remove(self, interaction, button):
        if not self.check(interaction):
            return await interaction.response.send_message("No permessi", ephemeral=True)

        data = load_porto()
        if not data:
            return await interaction.response.send_message("Nessun carico", ephemeral=True)

        await interaction.response.send_message("Seleziona carico da rimuovere:", view=RemoveView(list(data.keys())), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Porto(bot))