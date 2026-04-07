from discord.ext import commands
import os

class Admin(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def reload(self, ctx):

        for file in os.listdir("./cogs"):
            if file.endswith(".py") and file != "__init__.py":
                try:
                    await self.bot.reload_extension(f"cogs.{file[:-3]}")
                except:
                    await self.bot.load_extension(f"cogs.{file[:-3]}")

        await ctx.send("Cogs ricaricati!")

async def setup(bot):
    await bot.add_cog(Admin(bot))