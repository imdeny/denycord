import discord
from discord.ext import commands
from discord import app_commands

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_welcome_config(self, guild_id):
        result = self.bot.db.fetchone("SELECT channel_id, message_text FROM welcome_config WHERE guild_id = ?", (guild_id,))
        return result

    async def send_welcome_message(self, member, config):
        channel_id, message_text = config
        if not channel_id:
            return

        channel = member.guild.get_channel(channel_id)
        if channel:
            if message_text:
                # Format custom message
                description = message_text.format(
                    user=member.mention,
                    server=member.guild.name,
                    member_count=member.guild.member_count
                )
            else:
                description = f"Hello {member.mention}, welcome to the server! We're glad to have you here."

            embed = discord.Embed(
                title=f"Welcome to {member.guild.name}!",
                description=description,
                color=discord.Color.teal()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Member #{member.guild.member_count}")
            
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = self.get_welcome_config(member.guild.id)
        if config:
            await self.send_welcome_message(member, config)

    @app_commands.command(name="setwelcome", description="Sets the channel for welcome messages")
    @app_commands.describe(channel="The channel to send welcome messages in")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setwelcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if self.bot.db.fetchone("SELECT 1 FROM welcome_config WHERE guild_id = ?", (interaction.guild.id,)):
            self.bot.db.execute("UPDATE welcome_config SET channel_id = ? WHERE guild_id = ?", (channel.id, interaction.guild.id))
        else:
            self.bot.db.execute("INSERT INTO welcome_config (guild_id, channel_id) VALUES (?, ?)", (interaction.guild.id, channel.id))
            
        await interaction.response.send_message(f"Welcome messages will now be sent to {channel.mention}.")

    @app_commands.command(name="setwelcomemsg", description="Sets the custom welcome message")
    @app_commands.describe(message="The message (use {user}, {server}, {member_count})")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setwelcomemsg(self, interaction: discord.Interaction, message: str):
        if self.bot.db.fetchone("SELECT 1 FROM welcome_config WHERE guild_id = ?", (interaction.guild.id,)):
            self.bot.db.execute("UPDATE welcome_config SET message_text = ? WHERE guild_id = ?", (message, interaction.guild.id))
        else:
            self.bot.db.execute("INSERT INTO welcome_config (guild_id, message_text) VALUES (?, ?)", (interaction.guild.id, message))
        
        await interaction.response.send_message(f"Welcome message set to:\n{message}")

    @app_commands.command(name="testwelcome", description="Tests the welcome message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def testwelcome(self, interaction: discord.Interaction):
        config = self.get_welcome_config(interaction.guild.id)
        if config and config[0]: # config[0] is channel_id
            await interaction.response.send_message("Sending test welcome message...", ephemeral=True)
            await self.send_welcome_message(interaction.user, config)
        else:
            await interaction.response.send_message("Welcome channel is not set. Use `/setwelcome` to set it.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
