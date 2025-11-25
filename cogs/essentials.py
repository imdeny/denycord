import discord
from discord.ext import commands
from discord import app_commands
import random

class Essentials(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.locations = [
            "the US Space Station",
            "the Matrix Mainframe",
            "Gotham City Server",
            "Skynet Central Core",
            "Hogwarts WiFi",
            "the Death Star Comms",
            "Jarvis's Backend",
            "the TARDIS Console",
            "Wakanda's Network",
            "the Batcomputer",
            "Cerebro",
            "the OASIS",
            "HAL 9000's Memory",
            "R2-D2's Databank",
            "the Enterprise Bridge",
            "Cybertron's Core",
            "the Grid",
            "Aperture Science Labs",
            "Black Mesa Research Facility",
            "the Mushroom Kingdom",
            "Hyrule Castle",
            "the Citadel",
            "Norad",
            "Area 51",
            "the SCP Foundation Database",
            "Starlink Satellite #42",
            "Mars Rover Curiosity",
            "the Quantum Realm"
        ]

    @app_commands.command(name="ping", description="Replies with Pong! and latency info")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        location = random.choice(self.locations)
        await interaction.response.send_message(f"Pong! 🏓 **{latency}ms** from **{location}**")

    @app_commands.command(name="info", description="Shows information about the bot")
    async def info(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Bot Information", description="A comprehensive server bot.", color=discord.Color.blue())
        embed.add_field(name="Ping", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Essentials(bot))
