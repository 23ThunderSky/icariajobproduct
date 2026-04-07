from discord.ext import commands
import discord
import json
import os

DATA_FILE = "clientiporto.json"
CONFIG_FILE = "clientiporto_config.json"
PORTO_FILE = "porto.json"

ALLOWED_ROLES = [1315767688437436476, 1166815641790070794]

# ------------------- FILE -------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE) as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_porto():
    if not os.path.exists(PORTO_FILE):
        return {}
    with open(PORTO_FILE) as f:
        return json.load(f)

def save_porto(data):
    with open(PORTO_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {
            "channel_id": None,
            "message_id": None,
            "viaggi_channel_id": None
        }
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ------------------- EMBED CLIENTI -------------------
def create_embed(data):
    embed = discord.Embed(title="🚢 Clienti Porto", color=discord.Color.teal())
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

            stato = "✅" if consegnati >= max_camion and max_camion > 0 else "🚚"

            embed.add_field(
                name=f"{stato} {cliente}",
                value=f"{barra} {consegnati}/{max_camion}\nCarico: {info.get('carico')}\nViaggio: {info.get('viaggio')}\nPorto: {info.get('porto')}",
                inline=False
            )
    return embed

async def update_embed(bot):
    config = load_config()
    channel = bot.get_channel(config["channel_id"])
    if not channel:
        return
    try:
        msg = await channel.fetch_message(config["message_id"])
    except:
        return
    await msg.edit(embed=create_embed(load_data()), view=PortoView())

async def update_porto_embed(bot):
    try:
        from cogs.porto import update_porto_embed as porto_update
        await porto_update(bot)
    except:
        pass

# ------------------- MODAL -------------------
class ClienteModal(discord.ui.Modal, title="Aggiungi Cliente Porto"):
    cliente = discord.ui.TextInput(label="Cliente")
    carico = discord.ui.TextInput(label="Carico")
    viaggio = discord.ui.TextInput(label="Viaggio")
    porto = discord.ui.TextInput(label="Porto arrivo merce")
    camion = discord.ui.TextInput(label="Camion")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            camion = int(self.camion.value)
        except:
            camion = 0

        data = load_data()
        data[self.cliente.value] = {
            "consegnati": 0,
            "carico": self.carico.value,
            "viaggio": self.viaggio.value,
            "porto": self.porto.value,
            "camion": camion
        }
        save_data(data)

        porto_data = load_porto()
        key = f"{self.carico.value} ({self.porto.value})"
        if key not in porto_data:
            porto_data[key] = {"quantita": 0, "massimo": camion}
        save_porto(porto_data)

        await update_embed(interaction.client)
        await update_porto_embed(interaction.client)
        await interaction.response.send_message("✅ Cliente porto aggiunto!", ephemeral=True)

# ------------------- BOTTONI -------------------
class ConsegnaButton(discord.ui.Button):
    def __init__(self, cliente, message_id):
        super().__init__(label="✅ Consegna completata", style=discord.ButtonStyle.success)
        self.cliente = cliente
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        info = data[self.cliente]

        info["consegnati"] += 1
        save_data(data)

        await update_embed(interaction.client)
        await update_porto_embed(interaction.client)

        # Aggiorna messaggio viaggio originale immediatamente
        try:
            msg = await interaction.channel.fetch_message(self.message_id)
            new_embed = msg.embeds[0]
            new_embed.title = "🚢 Viaggio Porto consegnato ✅"
            await msg.edit(embed=new_embed, view=None)
        except:
            pass

        await interaction.response.send_message("✅ Viaggio consegnato!", ephemeral=True)

class AnnullaButton(discord.ui.Button):
    def __init__(self, cliente, message_id):
        super().__init__(label="🛑 Annulla viaggio", style=discord.ButtonStyle.danger)
        self.cliente = cliente
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        info = data[self.cliente]

        porto_data = load_porto()
        key = f"{info['carico']} ({info['porto']})"
        if key in porto_data:
            porto_data[key]["quantita"] += 1
            porto_data[key]["massimo"] += 1
            save_porto(porto_data)

        await update_porto_embed(interaction.client)

        # Aggiorna messaggio viaggio originale immediatamente
        try:
            msg = await interaction.channel.fetch_message(self.message_id)
            new_embed = msg.embeds[0]
            new_embed.title = "🚢 Viaggio Porto annullato ❌"
            await msg.edit(embed=new_embed, view=None)
        except:
            pass

        await interaction.response.send_message("❌ Viaggio annullato!", ephemeral=True)

class ViaggioView(discord.ui.View):
    def __init__(self, cliente, message_id):
        super().__init__(timeout=None)
        self.add_item(ConsegnaButton(cliente, message_id))
        self.add_item(AnnullaButton(cliente, message_id))

# ------------------- SELECT -------------------
class ClienteSelect(discord.ui.Select):
    def __init__(self, clienti):
        super().__init__(
            placeholder="Scegli cliente",
            options=[discord.SelectOption(label=c) for c in clienti]
        )

    async def callback(self, interaction: discord.Interaction):
        cliente = self.values[0]
        data = load_data()
        info = data[cliente]

        porto_data = load_porto()
        key = f"{info['carico']} ({info['porto']})"
        if key not in porto_data or porto_data[key]["quantita"] <= 0:
            return await interaction.response.send_message("❌ Nessuna merce disponibile!", ephemeral=True)

        porto_data[key]["quantita"] -= 1
        porto_data[key]["massimo"] -= 1
        save_porto(porto_data)
        await update_porto_embed(interaction.client)

        config = load_config()
        channel = interaction.client.get_channel(config.get("viaggi_channel_id"))

        embed = discord.Embed(title="🚢 Viaggio Porto Iniziato!", color=discord.Color.orange())
        embed.add_field(name="Cliente", value=cliente)
        embed.add_field(name="Carico", value=info["carico"])
        embed.add_field(name="Viaggio", value=info["viaggio"])
        embed.add_field(name="Porto", value=info["porto"])
        embed.add_field(name="Autista", value=interaction.user.mention)
        embed.set_footer(text="⚠️ Importante: il viaggio va creato su TruckersMP o altri programmi di creazione viaggi.")

        if channel:
            msg = await channel.send(embed=embed)
            view = ViaggioView(cliente, msg.id)
            await msg.edit(view=view)

        await interaction.response.send_message("🚢 Viaggio avviato!", ephemeral=True)

class ClienteSelectView(discord.ui.View):
    def __init__(self, clienti):
        super().__init__(timeout=60)
        self.add_item(ClienteSelect(clienti))

# ------------------- REMOVE -------------------
class RemoveSelect(discord.ui.Select):
    def __init__(self, clienti):
        super().__init__(
            placeholder="Scegli cliente da rimuovere",
            options=[discord.SelectOption(label=c) for c in clienti]
        )

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        porto_data = load_porto()
        cliente = self.values[0]

        if cliente in data:
            info = data[cliente]
            key = f"{info['carico']} ({info['porto']})"
            if key in porto_data:
                del porto_data[key]
                save_porto(porto_data)
            del data[cliente]
            save_data(data)

        await update_embed(interaction.client)
        await update_porto_embed(interaction.client)
        await interaction.response.send_message(f"Cliente **{cliente}** rimosso insieme al suo carico", ephemeral=True)

class RemoveView(discord.ui.View):
    def __init__(self, clienti):
        super().__init__(timeout=60)
        self.add_item(RemoveSelect(clienti))

# ------------------- VIEW -------------------
class PortoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def check(self, interaction):
        return any(role.id in ALLOWED_ROLES for role in interaction.user.roles)

    @discord.ui.button(label="➕ Aggiungi cliente", style=discord.ButtonStyle.success)
    async def add(self, interaction, button):
        if not self.check(interaction):
            return await interaction.response.send_message("No permessi", ephemeral=True)
        await interaction.response.send_modal(ClienteModal())

    @discord.ui.button(label="🚢 Inizia viaggio", style=discord.ButtonStyle.primary)
    async def viaggio(self, interaction, button):
        data = load_data()
        await interaction.response.send_message(
            view=ClienteSelectView(list(data.keys())),
            ephemeral=True
        )

    @discord.ui.button(label="➖ Rimuovi cliente", style=discord.ButtonStyle.danger)
    async def remove(self, interaction, button):
        data = load_data()
        await interaction.response.send_message(
            view=RemoveView(list(data.keys())),
            ephemeral=True
        )

# ------------------- COMMAND -------------------
class ClientiPorto(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def clientiporto(self, ctx):
        msg = await ctx.send(embed=create_embed(load_data()), view=PortoView())
        config = load_config()
        config["channel_id"] = ctx.channel.id
        config["message_id"] = msg.id
        save_config(config)

async def setup(bot):
    await bot.add_cog(ClientiPorto(bot))