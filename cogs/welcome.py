import discord
from discord.ext import commands
from discord import app_commands
import sqlite3

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_name = "bot_database.db"
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS welcome_config
                     (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
        conn.commit()
        conn.close()

    def get_welcome_channel(self, guild_id):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT channel_id FROM welcome_config WHERE guild_id = ?", (guild_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None

    async def send_welcome_message(self, member, channel_id):
        channel = member.guild.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title=f"Welcome to {member.guild.name}!",
                description=f"Hello {member.mention}, welcome to the server! We're glad to have you here.",
                color=discord.Color.teal()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Member #{member.guild.member_count}")
            
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel_id = self.get_welcome_channel(member.guild.id)
        if channel_id:
            await self.send_welcome_message(member, channel_id)

    @app_commands.command(name="setwelcome", description="Sets the channel for welcome messages")
    @app_commands.describe(channel="The channel to send welcome messages in")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setwelcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO welcome_config (guild_id, channel_id) VALUES (?, ?)", 
                  (interaction.guild.id, channel.id))
        conn.commit()
        conn.close()
        
        await interaction.response.send_message(f"Welcome messages will now be sent to {channel.mention}.")

    @app_commands.command(name="testwelcome", description="Tests the welcome message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def testwelcome(self, interaction: discord.Interaction):
        channel_id = self.get_welcome_channel(interaction.guild.id)
        if channel_id:
            await interaction.response.send_message("Sending test welcome message...", ephemeral=True)
            await self.send_welcome_message(interaction.user, channel_id)
        else:
            await interaction.response.send_message("Welcome channel is not set. Use `/setwelcome` to set it.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
