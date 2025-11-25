import discord
from discord.ext import commands
from discord import app_commands

class Essentials(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Replies with Pong!")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong!")

    @app_commands.command(name="info", description="Shows information about the bot")
    async def info(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Bot Information", description="A comprehensive server bot.", color=discord.Color.blue())
        embed.add_field(name="Ping", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Essentials(bot))
