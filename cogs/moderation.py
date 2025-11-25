import discord
from discord.ext import commands
from discord import app_commands

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="kick", description="Kicks a member from the server")
    @app_commands.describe(member="The member to kick", reason="The reason for kicking")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        if member == interaction.user:
            await interaction.response.send_message("You cannot kick yourself.", ephemeral=True)
            return
        
        try:
            await member.kick(reason=reason)
            await interaction.response.send_message(f"Kicked {member.mention} for reason: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to kick this user.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="ban", description="Bans a member from the server")
    @app_commands.describe(member="The member to ban", reason="The reason for banning")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        if member == interaction.user:
            await interaction.response.send_message("You cannot ban yourself.", ephemeral=True)
            return

        try:
            await member.ban(reason=reason)
            await interaction.response.send_message(f"Banned {member.mention} for reason: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to ban this user.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="clear", description="Clears a specified number of messages")
    @app_commands.describe(amount="The number of messages to clear")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        if amount < 1:
            await interaction.response.send_message("Amount must be at least 1.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)

    @app_commands.command(name="timeout", description="Timeouts a member")
    @app_commands.describe(member="The member to timeout", duration="Duration in minutes", reason="Reason for timeout")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = None):
        if member == interaction.user:
            await interaction.response.send_message("You cannot timeout yourself.", ephemeral=True)
            return
        
        try:
            from datetime import timedelta
            await member.timeout(timedelta(minutes=duration), reason=reason)
            await interaction.response.send_message(f"Timed out {member.mention} for {duration} minutes. Reason: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to timeout this user.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="untimeout", description="Removes timeout from a member")
    @app_commands.describe(member="The member to untimeout", reason="Reason for removing timeout")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        try:
            await member.timeout(None, reason=reason)
            await interaction.response.send_message(f"Removed timeout from {member.mention}.")
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to moderate this user.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="unban", description="Unbans a user")
    @app_commands.describe(user_id="The ID of the user to unban", reason="Reason for unbanning")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = None):
        try:
            user = await self.bot.fetch_user(user_id)
            await interaction.guild.unban(user, reason=reason)
            await interaction.response.send_message(f"Unbanned {user.mention}.")
        except discord.NotFound:
            await interaction.response.send_message("User not found.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to unban users.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="lock", description="Locks the current channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction):
        try:
            await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
            await interaction.response.send_message("Channel locked. 🔒")
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to manage channels.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="unlock", description="Unlocks the current channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        try:
            await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
            await interaction.response.send_message("Channel unlocked. 🔓")
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to manage channels.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="slowmode", description="Sets the slowmode delay for the channel")
    @app_commands.describe(seconds="Seconds for slowmode (0 to disable)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int):
        if seconds < 0 or seconds > 21600:
            await interaction.response.send_message("Slowmode must be between 0 and 21600 seconds.", ephemeral=True)
            return
        
        try:
            await interaction.channel.edit(slowmode_delay=seconds)
            if seconds == 0:
                await interaction.response.send_message("Slowmode disabled.")
            else:
                await interaction.response.send_message(f"Slowmode set to {seconds} seconds.")
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to manage channels.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="setnick", description="Changes a member's nickname")
    @app_commands.describe(member="The member to change nickname", nickname="The new nickname")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def setnick(self, interaction: discord.Interaction, member: discord.Member, nickname: str):
        try:
            await member.edit(nick=nickname)
            await interaction.response.send_message(f"Changed nickname for {member.mention} to {nickname}.")
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to manage nicknames.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="addrole", description="Adds a role to a member")
    @app_commands.describe(member="The member to add role to", role="The role to add")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def addrole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        try:
            await member.add_roles(role)
            await interaction.response.send_message(f"Added {role.mention} to {member.mention}.")
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to manage roles.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="removerole", description="Removes a role from a member")
    @app_commands.describe(member="The member to remove role from", role="The role to remove")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def removerole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        try:
            await member.remove_roles(role)
            await interaction.response.send_message(f"Removed {role.mention} from {member.mention}.")
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to manage roles.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
