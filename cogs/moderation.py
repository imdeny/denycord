import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import datetime

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_name = "bot_database.db"
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS mod_logs
                     (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS warnings
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, guild_id INTEGER, 
                      moderator_id INTEGER, reason TEXT, timestamp TIMESTAMP)''')
        conn.commit()
        conn.close()

    async def log_action(self, guild, embed):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT channel_id FROM mod_logs WHERE guild_id = ?", (guild.id,))
        result = c.fetchone()
        conn.close()

        if result:
            channel = guild.get_channel(result[0])
            if channel:
                await channel.send(embed=embed)

    @app_commands.command(name="setup_logs", description="Sets up the moderation logging channel")
    @app_commands.describe(channel="The channel to send mod logs to (leave empty to create one)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_logs(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if channel:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO mod_logs (guild_id, channel_id) VALUES (?, ?)", 
                      (interaction.guild.id, channel.id))
            conn.commit()
            conn.close()
            await interaction.response.send_message(f"Moderation logs will be sent to {channel.mention}.")
        else:
            # Create a new channel
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            try:
                channel = await interaction.guild.create_text_channel("mod-logs", overwrites=overwrites, reason="Setup mod logs")
                conn = sqlite3.connect(self.db_name)
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO mod_logs (guild_id, channel_id) VALUES (?, ?)", 
                          (interaction.guild.id, channel.id))
                conn.commit()
                conn.close()
                await interaction.response.send_message(f"Created {channel.mention} and set it as the logging channel.")
            except discord.Forbidden:
                 await interaction.response.send_message("I do not have permission to create channels.", ephemeral=True)

    # Listeners for logging
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or message.author.bot:
            return
        
        embed = discord.Embed(title="Message Deleted", color=discord.Color.red(), timestamp=datetime.datetime.now())
        embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
        embed.add_field(name="Content", value=message.content if message.content else "*Image/Embed*", inline=False)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="ID", value=message.id, inline=True)
        
        await self.log_action(message.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not before.guild or before.author.bot or before.content == after.content:
            return

        embed = discord.Embed(title="Message Edited", color=discord.Color.orange(), timestamp=datetime.datetime.now())
        embed.set_author(name=before.author.name, icon_url=before.author.display_avatar.url)
        embed.add_field(name="Before", value=before.content if before.content else "*Image/Embed*", inline=False)
        embed.add_field(name="After", value=after.content if after.content else "*Image/Embed*", inline=False)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Link", value=f"[Jump to Message]({after.jump_url})", inline=True)

        await self.log_action(before.guild, embed)
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        embed = discord.Embed(title="Member Banned", color=discord.Color.dark_red(), timestamp=datetime.datetime.now())
        embed.set_author(name=user.name, icon_url=user.display_avatar.url)
        embed.add_field(name="User ID", value=user.id, inline=False)
        await self.log_action(guild, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        embed = discord.Embed(title="Member Unbanned", color=discord.Color.green(), timestamp=datetime.datetime.now())
        embed.set_author(name=user.name, icon_url=user.display_avatar.url)
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
            
            # Log action
            embed = discord.Embed(title="Member Kicked", color=discord.Color.red(), timestamp=datetime.datetime.now())
            embed.set_author(name=member.name, icon_url=member.display_avatar.url)
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
            
            # Log action
            embed = discord.Embed(title="Member Banned", color=discord.Color.dark_red(), timestamp=datetime.datetime.now())
            embed.set_author(name=member.name, icon_url=member.display_avatar.url)
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
            from datetime import timedelta
            await member.timeout(timedelta(minutes=duration), reason=reason)
            await interaction.response.send_message(f"Timed out {member.mention} for {duration} minutes. Reason: {reason}")
            
            # Log action
            embed = discord.Embed(title="Member Timed Out", color=discord.Color.orange(), timestamp=datetime.datetime.now())
            embed.set_author(name=member.name, icon_url=member.display_avatar.url)
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
            
            # Log action
            embed = discord.Embed(title="Timeout Removed", color=discord.Color.green(), timestamp=datetime.datetime.now())
            embed.set_author(name=member.name, icon_url=member.display_avatar.url)
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
            
            # Log action
            embed = discord.Embed(title="Member Unbanned", color=discord.Color.green(), timestamp=datetime.datetime.now())
            embed.set_author(name=user.name, icon_url=user.display_avatar.url)
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
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("INSERT INTO warnings (user_id, guild_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
                  (member.id, interaction.guild.id, interaction.user.id, reason, datetime.datetime.now()))
        conn.commit()
        conn.close()
        
        await interaction.response.send_message(f"⚠️ Warned {member.mention} for: {reason}")
        
        # Log action
        embed = discord.Embed(title="Member Warned", color=discord.Color.yellow(), timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.display_avatar.url)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        await self.log_action(interaction.guild, embed)
        
        try:
             await member.send(f"You were warned in **{interaction.guild.name}** for: {reason}")
        except:
             pass

    @app_commands.command(name="warnings", description="View warnings for a member")
    @app_commands.describe(member="The member to view warnings for")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT id, moderator_id, reason, timestamp FROM warnings WHERE user_id = ? AND guild_id = ?", 
                  (member.id, interaction.guild.id))
        results = c.fetchall()
        conn.close()
        
        if not results:
            return await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)
            
        embed = discord.Embed(title=f"Warnings - {member.name}", color=discord.Color.orange())
        
        for warning_id, mod_id, reason, timestamp in results:
            mod = interaction.guild.get_member(mod_id)
            mod_name = mod.name if mod else f"User {mod_id}"
            # timestamp is stored as string/object, nice formatting handled by sqlite usually but lets be safe
            date_str = str(timestamp)[:16]
            embed.add_field(name=f"ID: {warning_id} | {date_str}", value=f"**Mod:** {mod_name}\n**Reason:** {reason}", inline=False)
            
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member")
    @app_commands.describe(member="The member to clear warnings for")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("DELETE FROM warnings WHERE user_id = ? AND guild_id = ?", (member.id, interaction.guild.id))
        deleted_count = c.rowcount
        conn.commit()
        conn.close()
        
        await interaction.response.send_message(f"Cleared {deleted_count} warnings for {member.mention}.")

    @app_commands.command(name="delwarn", description="Delete a specific warning by ID")
    @app_commands.describe(warning_id="The ID of the warning to delete")
    @app_commands.checks.has_permissions(administrator=True)
    async def delwarn(self, interaction: discord.Interaction, warning_id: int):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("DELETE FROM warnings WHERE id = ? AND guild_id = ?", (warning_id, interaction.guild.id))
        deleted_count = c.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            await interaction.response.send_message(f"Deleted warning ID {warning_id}.")
        else:
            await interaction.response.send_message(f"Warning ID {warning_id} not found.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
