import discord
from discord.ext import commands
from discord import app_commands
import random
import platform
import time
from datetime import timedelta

class Essentials(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
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
        current_time = time.time()
        uptime_seconds = int(current_time - self.start_time)
        uptime = str(timedelta(seconds=uptime_seconds))
        
        embed = discord.Embed(title="Bot Information", description="A comprehensive server bot.", color=discord.Color.blue())
        embed.add_field(name="Developer", value="Antigravity", inline=True)
        embed.add_field(name="Uptime", value=uptime, inline=True)
        embed.add_field(name="Ping", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Python Version", value=platform.python_version(), inline=True)
        embed.add_field(name="Discord.py Version", value=discord.__version__, inline=True)
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Users", value=str(sum(guild.member_count for guild in self.bot.guilds)), inline=True)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="Shows information about a member")
    @app_commands.describe(member="The member to get info for")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        roles = [role.mention for role in member.roles if role != interaction.guild.default_role]
        embed = discord.Embed(title=f"User Info - {member.name}", color=member.color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Nickname", value=member.nick, inline=True)
        embed.add_field(name="Created At", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
        embed.add_field(name="Joined At", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
        embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles) if roles else "None", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Shows information about the server")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title=f"Server Info - {guild.name}", color=discord.Color.gold())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="ID", value=guild.id, inline=True)
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Created At", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Displays a user's avatar")
    @app_commands.describe(member="The member to get avatar for")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        embed = discord.Embed(title=f"{member.name}'s Avatar", color=member.color)
        embed.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Essentials(bot))
