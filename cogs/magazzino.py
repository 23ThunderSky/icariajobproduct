from discord.ext import commands
import discord
import json
import os
import asyncio

DATA_FILE = "magazzino.json"
CONFIG_FILE = "magazzino_config.json"

ALLOWED_ROLES = [1315767688437436476]


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"channel_id": None, "message_id": None}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


def create_embed(data, produzioni=None):
    embed = discord.Embed(title="📦 Magazzino", color=discord.Color.blue())

    if not data:
        embed.description = "Nessun prodotto"
    else:
        for prodotto, info in data.items():
            quantita = info["quantita"]
            massimo = info["massimo"] if info["massimo"] > 0 else 1

            # Se il prodotto è in produzione, calcola barra progressiva dinamica
            if produzioni and prodotto in produzioni:
                prog = produzioni[prodotto]
                totale = prog["quantita_aggiunta"]
                rimanente = prog["durata_rimanente"]
                durata_totale = prog["durata_totale"]

                # Quantità prodotta finora durante countdown
                quantita_prod = int(totale * (durata_totale - rimanente) / durata_totale)
                barra_percent = (quantita + quantita_prod) / massimo
                verdi = round(barra_percent * 10)
                bianchi = 10 - verdi
                barra = "🟩" * verdi + "⬜" * bianchi
                numerico = f" {quantita + quantita_prod}/{massimo} ⏳ {rimanente}s"
                embed.add_field(name=f"🏭 {prodotto} in produzione", value=f"{barra}{numerico}", inline=False)
                continue

            # Barra normale per prodotti fermi
            percent = quantita / massimo
            verdi = round(percent * 10)
            bianchi = 10 - verdi
            barra = "🟩" * verdi + "⬜" * bianchi
            numerico = f" {quantita}/{massimo}"
            embed.add_field(name=prodotto, value=f"{barra}{numerico}", inline=False)

    return embed


async def update_magazzino_embed(bot, produzioni=None):
    data = load_data()
    config = load_config()
    channel = bot.get_channel(config["channel_id"])
    if not channel:
        return
    try:
        msg = await channel.fetch_message(config["message_id"])
    except:
        return

    embed = create_embed(data, produzioni=produzioni)
    view = MagazzinoView()
    await msg.edit(embed=embed, view=view)


class AddModal(discord.ui.Modal, title="Aggiungi / Modifica Prodotto"):
    prodotto = discord.ui.TextInput(label="Nome prodotto", placeholder="es. Latte")
    quantita = discord.ui.TextInput(label="Quantità da aggiungere", placeholder="es. 3")
    massimo = discord.ui.TextInput(label="Massimo stock", placeholder="es. 10")

    async def on_submit(self, interaction: discord.Interaction):
        data = load_data()
        nome = self.prodotto.value
        qty = int(self.quantita.value)
        massimo = int(self.massimo.value)

        if nome not in data:
            data[nome] = {"quantita": 0, "massimo": massimo}

        data[nome]["massimo"] = massimo
        save_data(data)

        # Avvia produzione
        asyncio.create_task(produzione_prodotto(interaction.client, nome, qty, massimo, durata=10))

        await interaction.response.send_message(f"Produzione di **{nome}** in corso!", ephemeral=True)


class RemoveSelect(discord.ui.Select):
    def __init__(self, prodotti):
        options = [discord.SelectOption(label=p) for p in prodotti]
        super().__init__(placeholder="Scegli prodotto da rimuovere", options=options)

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        prodotto = self.values[0]
        del data[prodotto]
        save_data(data)
        await update_magazzino_embed(interaction.client)
        await interaction.response.send_message(f"Prodotto **{prodotto}** rimosso.", ephemeral=True)


class RemoveView(discord.ui.View):
    def __init__(self, prodotti):
        super().__init__(timeout=60)
        self.add_item(RemoveSelect(prodotti))


class MagazzinoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def check_roles(self, interaction):
        user_roles = [role.id for role in interaction.user.roles]
        return any(role in ALLOWED_ROLES for role in user_roles)

    @discord.ui.button(label="➕ Aggiungi prodotto", style=discord.ButtonStyle.success)
    async def add(self, interaction: discord.Interaction, button):
        if not self.check_roles(interaction):
            await interaction.response.send_message("Non hai i permessi.", ephemeral=True)
            return
        await interaction.response.send_modal(AddModal())

    @discord.ui.button(label="➖ Rimuovi prodotto", style=discord.ButtonStyle.danger)
    async def remove(self, interaction: discord.Interaction, button):
        if not self.check_roles(interaction):
            await interaction.response.send_message("Non hai i permessi.", ephemeral=True)
            return
        data = load_data()
        if not data:
            await interaction.response.send_message("Nessun prodotto.", ephemeral=True)
            return
        view = RemoveView(list(data.keys()))
        await interaction.response.send_message("Seleziona prodotto da rimuovere:", view=view, ephemeral=True)


class Magazzino(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def magazzino(self, ctx):
        data = load_data()
        embed = create_embed(data)
        view = MagazzinoView()
        msg = await ctx.send(embed=embed, view=view)

        config = load_config()
        config["channel_id"] = ctx.channel.id
        config["message_id"] = msg.id
        save_config(config)


# PRODUZIONE CON COUNTDOWN
produzioni_attive = {}  # supporta più produzioni contemporanee

async def produzione_prodotto(bot, prodotto, quantita, massimo, durata=10):
    data = load_data()
    if prodotto not in data:
        data[prodotto] = {"quantita": 0, "massimo": massimo}
    data[prodotto]["massimo"] = massimo
    save_data(data)

    # Aggiungi produzione attiva
    produzioni_attive[prodotto] = {"quantita_aggiunta": quantita, "durata_rimanente": durata, "durata_totale": durata}

    while produzioni_attive[prodotto]["durata_rimanente"] > 0:
        await update_magazzino_embed(bot, produzioni_attive)
        await asyncio.sleep(1)
        produzioni_attive[prodotto]["durata_rimanente"] -= 1

    # Aggiorna quantità finale
    data[prodotto]["quantita"] += quantita
    if data[prodotto]["quantita"] > massimo:
        data[prodotto]["quantita"] = massimo
    save_data(data)

    # Rimuovi produzione attiva e aggiorna embed finale
    del produzioni_attive[prodotto]
    await update_magazzino_embed(bot)


async def setup(bot):
    await bot.add_cog(Magazzino(bot))