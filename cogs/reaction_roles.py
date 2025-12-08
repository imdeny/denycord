import discord
from discord.ext import commands
from discord import app_commands
import sqlite3

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_name = "bot_database.db"
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        # structure: message_id, role_id, emoji, channel_id
        c.execute('''CREATE TABLE IF NOT EXISTS reaction_roles
                     (message_id INTEGER, role_id INTEGER, emoji TEXT, channel_id INTEGER,
                      PRIMARY KEY (message_id, emoji))''')
        
        # Migration: Add channel_id if it doesn't exist
        try:
            c.execute("ALTER TABLE reaction_roles ADD COLUMN channel_id INTEGER")
        except sqlite3.OperationalError:
            pass # Column likely exists

        conn.commit()
        conn.close()

    @app_commands.command(name="rr_add", description="Add a reaction role to a message")
    @app_commands.describe(message_id="The ID of the message", role="The role to give", emoji="The emoji to react with")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rr_add(self, interaction: discord.Interaction, message_id: str, role: discord.Role, emoji: str):
        # Validate message_id
        try:
            msg_id = int(message_id)
            # Try to fetch message to ensure it exists and we have access
            message = await interaction.channel.fetch_message(msg_id)
        except (ValueError, discord.NotFound, discord.Forbidden):
            return await interaction.response.send_message("Invalid message ID or I cannot read that message.", ephemeral=True)

        # Database insert
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO reaction_roles (message_id, role_id, emoji, channel_id) VALUES (?, ?, ?, ?)", 
                      (msg_id, role.id, emoji, interaction.channel.id))
            conn.commit()
            
            # Add reaction to the message
            try:
                await message.add_reaction(emoji)
                await interaction.response.send_message(f"✅ Added reaction role: {emoji} -> {role.mention}", ephemeral=True)
            except discord.HTTPException:
                # If bot cannot react (e.g. invalid emoji)
                c.execute("DELETE FROM reaction_roles WHERE message_id = ? AND emoji = ?", (msg_id, emoji))
                conn.commit()
                await interaction.response.send_message("Failed to add reaction. Is the emoji valid and do I have permission?", ephemeral=True)
                
        except sqlite3.IntegrityError:
            await interaction.response.send_message("That emoji is already used for a role on this message.", ephemeral=True)
        finally:
            conn.close()

    @app_commands.command(name="rr_remove", description="Remove a reaction role from a message")
    @app_commands.describe(message_id="The ID of the message", emoji="The emoji to remove")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rr_remove(self, interaction: discord.Interaction, message_id: str, emoji: str):
        try:
            msg_id = int(message_id)
            message = await interaction.channel.fetch_message(msg_id)
        except (ValueError, discord.NotFound):
            # Even if message is not found, we might want to clean DB, but let's stick to safe path
            pass

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("DELETE FROM reaction_roles WHERE message_id = ? AND emoji = ?", (message_id, emoji))
        
        if c.rowcount > 0:
            conn.commit()
            # Try to remove reaction from bot
            try:
                if 'message' in locals():
                    await message.clear_reaction(emoji)
            except:
                pass
            await interaction.response.send_message(f"Removed reaction role for {emoji}.", ephemeral=True)
        else:
            await interaction.response.send_message("No reaction role found for that message and emoji.", ephemeral=True)
        conn.close()

    @app_commands.command(name="rr_list", description="List active reaction roles for this channel")
    async def rr_list(self, interaction: discord.Interaction):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        c.execute("SELECT message_id, role_id, emoji FROM reaction_roles WHERE channel_id = ?", (interaction.channel.id,))
        rows = c.fetchall()
        
        if not rows:
            # Fallback for old records without channel_id? 
            # If we just added the column, old records have NULL channel_id. 
            # We could try to fetch them if channel_id is NULL, or just accept they might not show up until re-added.
            # Let's try to fetch NULLs too just in case it's a migration, but it's risky if we are in another channel.
            # Better to just show current channel ones.
            conn.close()
            return await interaction.response.send_message("No reaction roles set up for this channel.", ephemeral=True)

        lines = []
        for msg_id, role_id, emoji in rows:
            role = interaction.guild.get_role(role_id)
            role_name = role.mention if role else f"Deleted Role ({role_id})"
            
            # Link to message for convenience
            msg_link = f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{msg_id}"
            lines.append(f"• {emoji} -> {role_name} [Jump to Message]({msg_link})")

        conn.close()
        
        # chunking
        msg = "Active Reaction Roles:\n" + "\n".join(lines)
        if len(msg) > 2000:
             msg = msg[:1990] + "..."
        
        await interaction.response.send_message(msg, ephemeral=True)

    # Listeners
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.member and payload.member.bot:
            return

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?", 
                  (payload.message_id, str(payload.emoji)))
        result = c.fetchone()
        conn.close()

        if result:
            role_id = result[0]
            guild = self.bot.get_guild(payload.guild_id)
            if guild:
                role = guild.get_role(role_id)
                member = payload.member 
                
                if role and member:
                    try:
                        await member.add_roles(role)
                    except discord.Forbidden:
                        pass # Bot missing perm

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?", 
                  (payload.message_id, str(payload.emoji)))
        result = c.fetchone()
        conn.close()

        if result:
            role_id = result[0]
            guild = self.bot.get_guild(payload.guild_id)
            if guild:
                role = guild.get_role(role_id)
                member = guild.get_member(payload.user_id)
                
                if role and member:
                    try:
                        await member.remove_roles(role)
                    except discord.Forbidden:
                        pass

async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
