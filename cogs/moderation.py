import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
from utils.helpers import make_mod_embed

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def log_action(self, guild, embed):
        result = self.bot.db.fetchone("SELECT channel_id FROM mod_logs WHERE guild_id = ?", (guild.id,))
        if result:
            channel = guild.get_channel(result[0])
            if channel:
                await channel.send(embed=embed)

    @app_commands.command(name="setup_logs", description="Sets up the moderation logging channel")
    @app_commands.describe(channel="The channel to send mod logs to (leave empty to create one)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_logs(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if channel:
            self.bot.db.execute("INSERT OR REPLACE INTO mod_logs (guild_id, channel_id) VALUES (?, ?)",
                      (interaction.guild.id, channel.id))
            await interaction.response.send_message(f"Moderation logs will be sent to {channel.mention}.")
        else:
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            try:
                channel = await interaction.guild.create_text_channel("mod-logs", overwrites=overwrites, reason="Setup mod logs")
                self.bot.db.execute("INSERT OR REPLACE INTO mod_logs (guild_id, channel_id) VALUES (?, ?)",
                          (interaction.guild.id, channel.id))
                await interaction.response.send_message(f"Created {channel.mention} and set it as the logging channel.")
            except discord.Forbidden:
                await interaction.response.send_message("I do not have permission to create channels.", ephemeral=True)

    # Listeners for logging
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or message.author.bot:
            return

        embed = make_mod_embed("Message Deleted", discord.Color.red(), message.author)
        embed.add_field(name="Content", value=message.content if message.content else "*Image/Embed*", inline=False)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="ID", value=message.id, inline=True)
        await self.log_action(message.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not before.guild or before.author.bot or before.content == after.content:
            return

        embed = make_mod_embed("Message Edited", discord.Color.orange(), before.author)
        embed.add_field(name="Before", value=before.content if before.content else "*Image/Embed*", inline=False)
        embed.add_field(name="After", value=after.content if after.content else "*Image/Embed*", inline=False)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Link", value=f"[Jump to Message]({after.jump_url})", inline=True)
        await self.log_action(before.guild, embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        embed = make_mod_embed("Member Banned", discord.Color.dark_red(), user)
        embed.add_field(name="User ID", value=user.id, inline=False)
        await self.log_action(guild, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        embed = make_mod_embed("Member Unbanned", discord.Color.green(), user)
        embed.add_field(name="User ID", value=user.id, inline=False)
        await self.log_action(guild, embed)

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

            embed = make_mod_embed("Member Kicked", discord.Color.red(), member)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)
            await self.log_action(interaction.guild, embed)

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

            embed = make_mod_embed("Member Banned", discord.Color.dark_red(), member)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)
            await self.log_action(interaction.guild, embed)

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
            await member.timeout(timedelta(minutes=duration), reason=reason)
            await interaction.response.send_message(f"Timed out {member.mention} for {duration} minutes. Reason: {reason}")

            embed = make_mod_embed("Member Timed Out", discord.Color.orange(), member)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Duration", value=f"{duration} minutes", inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)
            await self.log_action(interaction.guild, embed)

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

            embed = make_mod_embed("Timeout Removed", discord.Color.green(), member)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            await self.log_action(interaction.guild, embed)

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

            embed = make_mod_embed("Member Unbanned", discord.Color.green(), user)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)
            await self.log_action(interaction.guild, embed)

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

    @app_commands.command(name="warn", description="Warns a member")
    @app_commands.describe(member="The member to warn", reason="The reason for the warning")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        from datetime import datetime, timezone
        self.bot.db.execute(
            "INSERT INTO warnings (user_id, guild_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
            (member.id, interaction.guild.id, interaction.user.id, reason, datetime.now(timezone.utc)),
        )

        warn_count = self.bot.db.fetchone(
            "SELECT COUNT(*) FROM warnings WHERE user_id = ? AND guild_id = ?",
            (member.id, interaction.guild.id),
        )[0]

        await interaction.response.send_message(f"⚠️ Warned {member.mention} for: {reason} (Warning {warn_count})")

        embed = make_mod_embed("Member Warned", discord.Color.yellow(), member)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        embed.add_field(name="Total Warnings", value=str(warn_count), inline=True)
        await self.log_action(interaction.guild, embed)

        try:
            await member.send(f"You were warned in **{interaction.guild.name}** for: {reason} (Warning {warn_count})")
        except discord.Forbidden:
            pass

        # Check auto-mod action threshold
        action_config = self.bot.db.fetchone(
            "SELECT warn_threshold, action, duration_minutes FROM automod_actions WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if action_config:
            threshold, action, duration = action_config
            if warn_count >= threshold:
                auto_reason = f"Auto-{action}: reached {threshold} warnings"
                try:
                    if action == "kick":
                        await member.kick(reason=auto_reason)
                        await interaction.channel.send(f"Auto-kicked {member.mention} for reaching {threshold} warnings.")
                    elif action == "ban":
                        await member.ban(reason=auto_reason)
                        await interaction.channel.send(f"Auto-banned {member.mention} for reaching {threshold} warnings.")
                    elif action == "timeout":
                        await member.timeout(timedelta(minutes=duration), reason=auto_reason)
                        await interaction.channel.send(f"Auto-timed out {member.mention} for {duration} minutes (reached {threshold} warnings).")
                except discord.Forbidden:
                    await interaction.channel.send(f"Could not auto-{action} {member.mention}: missing permissions.")

    @app_commands.command(name="setup_automod_action", description="Auto-punish members when warnings reach a threshold")
    @app_commands.describe(threshold="Number of warnings to trigger the action", action="Punishment to apply", duration="Timeout duration in minutes (timeout action only)")
    @app_commands.choices(action=[
        app_commands.Choice(name="Timeout", value="timeout"),
        app_commands.Choice(name="Kick", value="kick"),
        app_commands.Choice(name="Ban", value="ban"),
        app_commands.Choice(name="Disable", value="disable"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_automod_action(self, interaction: discord.Interaction, threshold: int, action: str, duration: int = 60):
        if action == "disable":
            self.bot.db.execute("DELETE FROM automod_actions WHERE guild_id = ?", (interaction.guild.id,))
            return await interaction.response.send_message("Auto-mod actions disabled.")

        self.bot.db.execute(
            "INSERT OR REPLACE INTO automod_actions (guild_id, warn_threshold, action, duration_minutes) VALUES (?, ?, ?, ?)",
            (interaction.guild.id, threshold, action, duration),
        )
        msg = f"Auto-mod action set: **{action}** triggers at **{threshold}** warnings."
        if action == "timeout":
            msg += f" Duration: **{duration} minutes**."
        await interaction.response.send_message(msg)

    @app_commands.command(name="warnings", description="View warnings for a member")
    @app_commands.describe(member="The member to view warnings for")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        results = self.bot.db.fetchall(
            "SELECT id, moderator_id, reason, timestamp FROM warnings WHERE user_id = ? AND guild_id = ?",
            (member.id, interaction.guild.id),
        )

        if not results:
            return await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)

        embed = discord.Embed(title=f"Warnings - {member.name}", color=discord.Color.orange())
        for warning_id, mod_id, reason, timestamp in results:
            mod = interaction.guild.get_member(mod_id)
            mod_name = mod.name if mod else f"User {mod_id}"
            date_str = str(timestamp)[:16]
            embed.add_field(name=f"ID: {warning_id} | {date_str}", value=f"**Mod:** {mod_name}\n**Reason:** {reason}", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member")
    @app_commands.describe(member="The member to clear warnings for")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        c = self.bot.db.execute("DELETE FROM warnings WHERE user_id = ? AND guild_id = ?", (member.id, interaction.guild.id))
        await interaction.response.send_message(f"Cleared {c.rowcount} warnings for {member.mention}.")

    @app_commands.command(name="delwarn", description="Delete a specific warning by ID")
    @app_commands.describe(warning_id="The ID of the warning to delete")
    @app_commands.checks.has_permissions(administrator=True)
    async def delwarn(self, interaction: discord.Interaction, warning_id: int):
        c = self.bot.db.execute("DELETE FROM warnings WHERE id = ? AND guild_id = ?", (warning_id, interaction.guild.id))
        if c.rowcount > 0:
            await interaction.response.send_message(f"Deleted warning ID {warning_id}.")
        else:
            await interaction.response.send_message(f"Warning ID {warning_id} not found.", ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or before.channel == after.channel:
            return

        if before.channel is None:
            embed = make_mod_embed("Joined Voice", discord.Color.green(), member)
            embed.add_field(name="Channel", value=after.channel.mention, inline=True)
        elif after.channel is None:
            embed = make_mod_embed("Left Voice", discord.Color.red(), member)
            embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        else:
            embed = make_mod_embed("Moved Voice Channel", discord.Color.orange(), member)
            embed.add_field(name="From", value=before.channel.mention, inline=True)
            embed.add_field(name="To", value=after.channel.mention, inline=True)

        await self.log_action(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.bot:
            return

        if before.nick != after.nick:
            embed = make_mod_embed("Nickname Changed", discord.Color.blue(), after)
            embed.add_field(name="Before", value=before.nick or before.name, inline=True)
            embed.add_field(name="After", value=after.nick or after.name, inline=True)
            await self.log_action(after.guild, embed)

        added_roles = [r for r in after.roles if r not in before.roles]
        removed_roles = [r for r in before.roles if r not in after.roles]

        if added_roles:
            embed = make_mod_embed("Roles Added", discord.Color.green(), after)
            embed.add_field(name="Roles", value=", ".join(r.mention for r in added_roles), inline=False)
            await self.log_action(after.guild, embed)

        if removed_roles:
            embed = make_mod_embed("Roles Removed", discord.Color.red(), after)
            embed.add_field(name="Roles", value=", ".join(r.mention for r in removed_roles), inline=False)
            await self.log_action(after.guild, embed)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
