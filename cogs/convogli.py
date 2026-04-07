from discord.ext import commands, tasks
import discord
import json
import os
from datetime import datetime, timedelta
import pytz

CONVOGLI_FILE = "convogli.json"
CONFIG_FILE = "convogli_config.json"
ALLOWED_ROLE = 1166815641790070794  # admin

# ------------------- FILE -------------------
def load_convogli():
    if not os.path.exists(CONVOGLI_FILE):
        return []
    try:
        with open(CONVOGLI_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_convogli(data):
    with open(CONVOGLI_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"channel_id": None}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"channel_id": None}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ------------------- MODAL AGGIUNGI -------------------
class ConvoglioModal(discord.ui.Modal, title="Aggiungi Convoglio"):
    data = discord.ui.TextInput(label="Data (12/09/26)", required=True)
    orario = discord.ui.TextInput(label="Orario ritrovo (21:30)", required=True)
    nome = discord.ui.TextInput(label="Nome convoglio", required=True)
    link = discord.ui.TextInput(label="TruckersMP link", required=True)
    info = discord.ui.TextInput(label="Info (opzionale)", required=False, style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        tz = pytz.timezone("Europe/Rome")
        try:
            dt = datetime.strptime(f"{self.data.value} {self.orario.value}", "%d/%m/%y %H:%M")
            dt = tz.localize(dt)
        except:
            return await interaction.response.send_message("❌ Formato data/orario non valido", ephemeral=True)

        convogli = load_convogli()
        nuovo = {
            "data": self.data.value,
            "orario": self.orario.value,
            "datetime_iso": dt.isoformat(),
            "nome": self.nome.value,
            "link": self.link.value,
            "info": self.info.value,
            "notificato": False
        }
        convogli.append(nuovo)
        save_convogli(convogli)

        await interaction.response.send_message("✅ Convoglio aggiunto!", ephemeral=True)
        await update_convogli_message(interaction.channel)

# ------------------- MODAL MODIFICA -------------------
class ModificaConvoglioModal(discord.ui.Modal):
    def __init__(self, convoglio):
        super().__init__(title=f"Modifica {convoglio['nome']}")
        self.convoglio = convoglio

        self.data = discord.ui.TextInput(label="Data (12/09/26)", required=True, default=convoglio["data"])
        self.orario = discord.ui.TextInput(label="Orario ritrovo (21:30)", required=True, default=convoglio["orario"])
        self.nome = discord.ui.TextInput(label="Nome convoglio", required=True, default=convoglio["nome"])
        self.link = discord.ui.TextInput(label="TruckersMP link", required=True, default=convoglio["link"])
        self.info = discord.ui.TextInput(label="Info (opzionale)", required=False, style=discord.TextStyle.paragraph, default=convoglio.get("info",""))

        self.add_item(self.data)
        self.add_item(self.orario)
        self.add_item(self.nome)
        self.add_item(self.link)
        self.add_item(self.info)

    async def on_submit(self, interaction: discord.Interaction):
        tz = pytz.timezone("Europe/Rome")
        try:
            dt = datetime.strptime(f"{self.data.value} {self.orario.value}", "%d/%m/%y %H:%M")
            dt = tz.localize(dt)
        except:
            return await interaction.response.send_message("❌ Formato data/orario non valido", ephemeral=True)

        convogli = load_convogli()
        for c in convogli:
            if c == self.convoglio:
                c["data"] = self.data.value
                c["orario"] = self.orario.value
                c["datetime_iso"] = dt.isoformat()
                c["nome"] = self.nome.value
                c["link"] = self.link.value
                c["info"] = self.info.value
                c["notificato"] = False
                break
        save_convogli(convogli)
        await interaction.response.send_message("✅ Convoglio modificato!", ephemeral=True)
        await update_convogli_message(interaction.channel)

# ------------------- MODAL SET CANALE -------------------
class SetChannelModal(discord.ui.Modal, title="Imposta Canale Notifiche"):
    channel_id = discord.ui.TextInput(label="ID Canale", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cid = int(self.channel_id.value)
        except:
            return await interaction.response.send_message("❌ ID non valido", ephemeral=True)

        config = load_config()
        config["channel_id"] = cid
        save_config(config)

        await interaction.response.send_message("✅ Canale impostato!", ephemeral=True)

# ------------------- VIEW -------------------
class ConvogliView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def check_role(self, interaction):
        return any(role.id == ALLOWED_ROLE for role in interaction.user.roles)

    @discord.ui.button(label="➕ Aggiungi convoglio", style=discord.ButtonStyle.success)
    async def add(self, interaction: discord.Interaction, button):
        if not self.check_role(interaction):
            return await interaction.response.send_message("❌ Non hai il permesso", ephemeral=True)
        await interaction.response.send_modal(ConvoglioModal())

    @discord.ui.button(label="📋 Lista convogli", style=discord.ButtonStyle.primary)
    async def lista(self, interaction: discord.Interaction, button):
        convogli = load_convogli()
        if not convogli:
            return await interaction.response.send_message("Nessun convoglio", ephemeral=True)
        for c in convogli:
            embed = discord.Embed(title=f"🚚 {c['nome']}", color=discord.Color.orange())
            embed.add_field(name="Ritrovo", value=f"{c['data']} {c['orario']}", inline=False)
            embed.add_field(name="Link", value=f"[TruckersMP]({c['link']})", inline=False)
            embed.add_field(name="Info", value=c.get('info','Nessuna info'), inline=False)
            view = ConvoglioActionView(c)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="📍 Imposta canale notifiche", style=discord.ButtonStyle.secondary)
    async def set_channel(self, interaction: discord.Interaction, button):
        if not self.check_role(interaction):
            return await interaction.response.send_message("❌ Non hai il permesso", ephemeral=True)
        await interaction.response.send_modal(SetChannelModal())

# ------------------- VIEW PULSANTI SINGOLO CONVOGLIO -------------------
class ConvoglioActionView(discord.ui.View):
    def __init__(self, convoglio):
        super().__init__(timeout=None)
        self.convoglio = convoglio

    @discord.ui.button(label="✏️ Modifica", style=discord.ButtonStyle.primary)
    async def modifica(self, interaction: discord.Interaction, button):
        if not any(role.id == ALLOWED_ROLE for role in interaction.user.roles):
            return await interaction.response.send_message("❌ Non hai il permesso", ephemeral=True)
        await interaction.response.send_modal(ModificaConvoglioModal(self.convoglio))

    @discord.ui.button(label="🗑️ Rimuovi", style=discord.ButtonStyle.danger)
    async def rimuovi(self, interaction: discord.Interaction, button):
        if not any(role.id == ALLOWED_ROLE for role in interaction.user.roles):
            return await interaction.response.send_message("❌ Non hai il permesso", ephemeral=True)
        convogli = load_convogli()
        convogli = [c for c in convogli if c != self.convoglio]
        save_convogli(convogli)
        await interaction.response.send_message("✅ Convoglio rimosso", ephemeral=True)
        await update_convogli_message(interaction.channel)

# ------------------- MESSAGGIO DINAMICO -------------------
async def update_convogli_message(channel):
    async for msg in channel.history(limit=20):
        if msg.author == channel.guild.me:
            try:
                await msg.delete()
            except:
                pass
    await channel.send("🚚 **Gestione Convogli**", view=ConvogliView())

# ------------------- COG -------------------
class Convogli(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_convogli.start()

    def cog_unload(self):
        self.check_convogli.cancel()

    @commands.command()
    async def convogli(self, ctx):
        await update_convogli_message(ctx.channel)

    @tasks.loop(seconds=30)
    async def check_convogli(self):
        convogli = load_convogli()
        config = load_config()
        if not config.get("channel_id"):
            return
        channel = self.bot.get_channel(config["channel_id"])
        if not channel:
            return

        now = datetime.now(pytz.timezone("Europe/Rome"))
        updated = False
        for c in convogli:
            if c.get("notificato"):
                continue
            try:
                dt = datetime.fromisoformat(c["datetime_iso"])
            except:
                continue
            if dt - timedelta(minutes=1) <= now <= dt:
                await channel.send(
                    f"@everyone ⏰ Tra 1 minuto inizia il convoglio **{c['nome']}**!\n📅 {c['data']} {c['orario']}\n[Link TruckersMP]({c['link']})\n{c.get('info','Nessuna info')}"
                )
                c["notificato"] = True
                updated = True
        if updated:
            save_convogli(convogli)

# ------------------- SETUP -------------------
async def setup(bot):
    await bot.add_cog(Convogli(bot))