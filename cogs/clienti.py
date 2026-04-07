from discord.ext import commands
import discord
import json
import os
import asyncio

DATA_FILE = "clienti.json"
CONFIG_FILE = "clienti_config.json"
MAGAZZINO_FILE = "magazzino.json"

ALLOWED_ROLES = [1315767688437436476, 1166815641790070794]

# ------------------- File Management -------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE) as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_magazzino():
    if not os.path.exists(MAGAZZINO_FILE):
        return {}
    with open(MAGAZZINO_FILE) as f:
        return json.load(f)

def save_magazzino(data):
    with open(MAGAZZINO_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {
            "channel_id": None,
            "message_id": None,
            "magazzino_message_id": None,
            "magazzino_channel_id": None,
            "viaggi_channel_id": None
        }
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ------------------- MAGAZZINO -------------------
def create_magazzino_embed(data):
    embed = discord.Embed(title="📦 Magazzino", color=discord.Color.blue())
    for prodotto, info in data.items():
        quantita = info.get("quantita", 0)
        massimo = info.get("massimo", 10)
        percent = quantita / massimo if massimo > 0 else 0
        verdi = round(percent * 10)
        bianchi = 10 - verdi
        barra = "🟩" * verdi + "⬜" * bianchi
        embed.add_field(name=prodotto, value=f"{barra} {quantita}/{massimo}", inline=False)
    return embed

async def update_magazzino_message(bot):
    config = load_config()

    channel_id = config.get("magazzino_channel_id")
    message_id = config.get("magazzino_message_id")

    if not channel_id or not message_id:
        return

    channel = bot.get_channel(channel_id)
    if not channel:
        return

    try:
        msg = await channel.fetch_message(message_id)
    except:
        return

    await msg.edit(embed=create_magazzino_embed(load_magazzino()))

# ------------------- CLIENTI -------------------
def create_embed(data):
    embed = discord.Embed(title="🚚 Clienti", color=discord.Color.green())
    if not data:
        embed.description = "Nessun cliente"
    else:
        for cliente, info in data.items():
            consegnati = info.get("consegnati", 0)
            max_camion = info.get("camion", 0)
            total = max_camion if max_camion > 0 else 1
            percent = consegnati / total
            verdi = round(percent * 10)
            bianchi = 10 - verdi
            barra = "🟩" * verdi + "⬜" * bianchi
            embed.add_field(
                name=cliente,
                value=f"{barra} {consegnati}/{max_camion} consegnati\nCarico: {info.get('carico')}\nViaggio: {info.get('viaggio')}\nMax camion da inviare: {max_camion}",
                inline=False
            )
    return embed

async def update_clienti_embed(bot):
    config = load_config()
    channel = bot.get_channel(config["channel_id"])
    if not channel:
        return
    try:
        msg = await channel.fetch_message(config["message_id"])
    except:
        return
    await msg.edit(embed=create_embed(load_data()), view=ClientiView())

# ------------------- MODAL -------------------
class ClienteInfoModal(discord.ui.Modal):
    def __init__(self, carico):
        super().__init__(title="Aggiungi Cliente")
        self.carico = carico
        self.cliente = discord.ui.TextInput(label="Cliente")
        self.viaggio = discord.ui.TextInput(label="Viaggio")
        self.camion = discord.ui.TextInput(label="Camion da inviare")
        self.add_item(self.cliente)
        self.add_item(self.viaggio)
        self.add_item(self.camion)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            camion = int(self.camion.value)
        except:
            camion = 0
        data = load_data()
        data[self.cliente.value] = {
            "consegnati": 0,
            "carico": self.carico,
            "viaggio": self.viaggio.value,
            "camion": camion
        }
        save_data(data)
        await update_clienti_embed(interaction.client)
        await interaction.response.send_message("✅ Cliente aggiunto!", ephemeral=True)

# ------------------- SELECT CARICO -------------------
class CaricoSelect(discord.ui.Select):
    def __init__(self, prodotti):
        super().__init__(placeholder="Seleziona carico", options=[discord.SelectOption(label=p) for p in prodotti])

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ClienteInfoModal(self.values[0]))

class CaricoSelectView(discord.ui.View):
    def __init__(self, prodotti):
        super().__init__(timeout=60)
        self.add_item(CaricoSelect(prodotti))

# ------------------- ANNULLA -------------------
class AnnullaViaggioButton(discord.ui.Button):
    def __init__(self, autista, cliente, carico):
        super().__init__(label="🛑 Annulla viaggio", style=discord.ButtonStyle.danger)
        self.autista = autista
        self.cliente = cliente
        self.carico = carico

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.autista and not any(role.id in ALLOWED_ROLES for role in interaction.user.roles):
            return await interaction.response.send_message("Non puoi annullare.", ephemeral=True)
        magazzino = load_magazzino()
        magazzino[self.carico]["quantita"] += 1
        save_magazzino(magazzino)
        await update_magazzino_message(interaction.client)
        await interaction.response.edit_message(
            content=f"❌ Viaggio verso **{self.cliente}** annullato.\nProdotto **{self.carico}** reinserito nel magazzino.",
            embed=None,
            view=None
        )

class AnnullaView(discord.ui.View):
    def __init__(self, autista, cliente, carico):
        super().__init__(timeout=None)
        self.add_item(AnnullaViaggioButton(autista, cliente, carico))

# ------------------- CONSEGNA -------------------
class ClienteSelect(discord.ui.Select):
    def __init__(self, clienti):
        super().__init__(placeholder="Scegli cliente", options=[discord.SelectOption(label=c) for c in clienti])

    async def callback(self, interaction: discord.Interaction):
        cliente = self.values[0]
        data = load_data()
        info = data[cliente]
        carico = info["carico"]

        # 🔴 CONTROLLO LIMITE CONSEGNE
        consegnati = info.get("consegnati", 0)
        max_camion = info.get("camion", 0)

        if max_camion > 0 and consegnati >= max_camion:
            return await interaction.response.send_message(
                "❌ Errore, il cliente ha già ricevuto tutta la merce che ha richiesto, prego scegli un altro cliente a cui spedire.",
                ephemeral=True
            )

        magazzino = load_magazzino()
        if magazzino.get(carico, {}).get("quantita", 0) <= 0:
            return await interaction.response.send_message("❌ Magazzino vuoto!", ephemeral=True)

        magazzino[carico]["quantita"] -= 1
        save_magazzino(magazzino)
        await update_magazzino_message(interaction.client)

        # Canale viaggi separato
        config = load_config()
        viaggi_channel_id = config.get("viaggi_channel_id")
        viaggi_channel = interaction.client.get_channel(viaggi_channel_id)
        if not viaggi_channel:
            return await interaction.response.send_message("⚠️ Canale viaggi non configurato!", ephemeral=True)

        # Embed viaggio finale inviato nel canale viaggi
        embed = discord.Embed(title="🚛 Viaggio Iniziato!", color=discord.Color.orange())
        embed.add_field(name="Cliente", value=cliente, inline=False)
        embed.add_field(name="Carico", value=carico, inline=False)
        embed.add_field(name="Viaggio", value=info.get("viaggio", "N/A"), inline=False)
        embed.add_field(name="Autista", value=interaction.user.mention, inline=False)
        embed.set_footer(text="⚠️ Importante: il viaggio va creato su TruckersMP o altri programmi.")

        await viaggi_channel.send(embed=embed, view=AnnullaView(interaction.user, cliente, carico))

        await interaction.response.send_message("✅ Viaggio avviato e inviato nel canale viaggi.", ephemeral=True)


class ClienteSelectView(discord.ui.View):
    def __init__(self, clienti):
        super().__init__(timeout=60)
        self.add_item(ClienteSelect(clienti))

# ------------------- RIMUOVI -------------------
class RemoveSelect(discord.ui.Select):
    def __init__(self, clienti):
        super().__init__(placeholder="Scegli cliente da rimuovere", options=[discord.SelectOption(label=c) for c in clienti])

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        cliente = self.values[0]
        del data[cliente]
        save_data(data)
        await update_clienti_embed(interaction.client)
        await interaction.response.send_message(f"Cliente **{cliente}** rimosso", ephemeral=True)

class RemoveView(discord.ui.View):
    def __init__(self, clienti):
        super().__init__(timeout=60)
        self.add_item(RemoveSelect(clienti))

# ------------------- CONSEGNA COMPLETATA -------------------
class ConsegnaButton(discord.ui.Button):
    def __init__(self, autista, cliente):
        super().__init__(label="✅ Consegna completata", style=discord.ButtonStyle.success)
        self.autista = autista
        self.cliente = cliente

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.autista and not any(role.id in ALLOWED_ROLES for role in interaction.user.roles):
            return await interaction.response.send_message("Non puoi completare questa consegna.", ephemeral=True)
        data = load_data()
        if self.cliente in data:
            data[self.cliente]["consegnati"] += 1
            save_data(data)
            await update_clienti_embed(interaction.client)
        embed = discord.Embed(title="✅ Viaggio Completato!", color=discord.Color.green())
        info = data[self.cliente]
        embed.add_field(name="Cliente", value=self.cliente, inline=False)
        embed.add_field(name="Carico", value=info.get("carico"), inline=False)
        embed.add_field(name="Viaggio", value=info.get("viaggio"), inline=False)
        embed.add_field(name="Autista", value=self.autista.mention, inline=False)
        embed.set_footer(text="⚠️ Viaggio completato correttamente!")
        view = discord.ui.View()
        for child in self.view.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=view)

class AnnullaView(discord.ui.View):
    def __init__(self, autista, cliente, carico):
        super().__init__(timeout=None)
        self.add_item(AnnullaViaggioButton(autista, cliente, carico))
        self.add_item(ConsegnaButton(autista, cliente))

# ------------------- VIEW -------------------
class ClientiView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def check_roles(self, interaction):
        return any(role.id in ALLOWED_ROLES for role in interaction.user.roles)

    @discord.ui.button(label="➕ Aggiungi cliente", style=discord.ButtonStyle.success)
    async def add(self, interaction, button):
        if not self.check_roles(interaction):
            return await interaction.response.send_message("No permessi", ephemeral=True)
        prodotti = list(load_magazzino().keys())
        await interaction.response.send_message(view=CaricoSelectView(prodotti), ephemeral=True)

    @discord.ui.button(label="🚚 Inizia consegna", style=discord.ButtonStyle.primary)
    async def consegna(self, interaction, button):
        data = load_data()
        await interaction.response.send_message(view=ClienteSelectView(list(data.keys())), ephemeral=True)

    @discord.ui.button(label="➖ Rimuovi cliente", style=discord.ButtonStyle.danger)
    async def remove(self, interaction, button):
        data = load_data()
        await interaction.response.send_message(view=RemoveView(list(data.keys())), ephemeral=True)

# ------------------- COMMAND -------------------
class Clienti(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def clienti(self, ctx):
        await ctx.send("📩 Inserisci ID messaggio MAGAZZINO:")
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        msg_id = await self.bot.wait_for("message", check=check)
        config = load_config()

        # Salva correttamente sia ID messaggio che canale magazzino
        config["magazzino_message_id"] = int(msg_id.content)
        config["magazzino_channel_id"] = ctx.channel.id

        # Invia messaggio clienti
        msg = await ctx.send(embed=create_embed(load_data()), view=ClientiView())
        config["channel_id"] = ctx.channel.id
        config["message_id"] = msg.id
        save_config(config)

async def setup(bot):
    await bot.add_cog(Clienti(bot))