import discord
from discord.ext import commands
from discord import app_commands
import datetime
import asyncio

class TicketPanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.processing = set()

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="ticket_create", emoji="📩")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.processing:
            return await interaction.response.send_message("Please wait, your ticket is being created...", ephemeral=True)
            
        self.processing.add(interaction.user.id)
        try:
            await interaction.response.defer(ephemeral=True)
            
            # 1. Fetch settings
            settings = self.bot.db.fetchone("SELECT active_category_id FROM ticket_settings WHERE guild_id = ?", (interaction.guild.id,))
            if not settings:
                return await interaction.followup.send("Ticket system not set up. Please ask an admin to run `/ticket setup`.", ephemeral=True)
            
            category_id = settings[0]
            category = interaction.guild.get_channel(category_id)
            
            if not category:
                 return await interaction.followup.send("Ticket category not found. Setup might be broken.", ephemeral=True)

            # 2. Check for existing open tickets
            existing_ticket = self.bot.db.fetchone("SELECT channel_id FROM tickets WHERE guild_id = ? AND owner_id = ? AND status = 'OPEN'", 
                                                 (interaction.guild.id, interaction.user.id))
            if existing_ticket:
                channel = interaction.guild.get_channel(existing_ticket[0])
                if channel:
                    return await interaction.followup.send(f"You already have an open ticket: {channel.mention}", ephemeral=True)
                else:
                    # Cleanup ghost ticket from DB if channel is gone
                    self.bot.db.execute("UPDATE tickets SET status = 'CLOSED' WHERE channel_id = ?", (existing_ticket[0],))
            
            # 3. Create Ticket Channel
            # Permissions: Everyone NO, User YES, Staff YES (Inherited from category usually, but let's be explicit)
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
            }
            
            try:
                channel_name = f"ticket-{interaction.user.name}"
                ticket_channel = await interaction.guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
                
                # 4. Log to DB
                self.bot.db.execute("INSERT INTO tickets (channel_id, guild_id, owner_id, status, created_at) VALUES (?, ?, ?, ?, ?)",
                                    (ticket_channel.id, interaction.guild.id, interaction.user.id, "OPEN", datetime.datetime.now()))
                
                # 5. Send Welcome Message
                embed = discord.Embed(title=f"Ticket - {interaction.user.name}", description="Support will be with you shortly.\nClick below to close this ticket.", color=discord.Color.green())
                await ticket_channel.send(f"{interaction.user.mention}", embed=embed, view=TicketControlView(self.bot))
                
                await interaction.followup.send(f"Ticket created: {ticket_channel.mention}", ephemeral=True)
                
            except Exception as e:
                await interaction.followup.send(f"Failed to create ticket: {e}", ephemeral=True)
        finally:
            if interaction.user.id in self.processing:
                self.processing.remove(interaction.user.id)

class TicketControlView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="ticket_close", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Fetch archive category
        settings = self.bot.db.fetchone("SELECT archive_category_id FROM ticket_settings WHERE guild_id = ?", (interaction.guild.id,))
        if not settings:
             return await interaction.response.send_message("Archive category not found.", ephemeral=True)
        
        archive_cat_id = settings[0]
        archive_cat = interaction.guild.get_channel(archive_cat_id)
        
        if not archive_cat:
            return await interaction.response.send_message("Archive category removed. Cannot archive.", ephemeral=True)
            
        await interaction.response.defer()
        
        try:
            # Move to archive with sync_permissions=True
            # This wipes channel-specific overwrites and inherits from Category (which is Admin-only)
            await interaction.channel.edit(category=archive_cat, sync_permissions=True)
            
            # Update DB
            self.bot.db.execute("UPDATE tickets SET status = 'CLOSED' WHERE channel_id = ?", (interaction.channel.id,))
            
            await interaction.followup.send("Ticket closed and archived. 🔒")
            
            # Stop the view interactions (cleanup)
            self.stop()
            
        except Exception as e:
             await interaction.followup.send(f"Error closing ticket: {e}")

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Register persistent views
        self.bot.add_view(TicketPanelView(bot))
        self.bot.add_view(TicketControlView(bot))

    def is_staff(self, member):
        return member.guild_permissions.administrator or \
               member.guild_permissions.ban_members or \
               member.guild_permissions.kick_members

    @app_commands.command(name="ticket_setup", description="Setup ticket categories and panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        
        try:
            # 1. Create Categories
            # Active: Staff Only (View)
            active_overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
            }
            # Add implicit staff access via roles? No, let's trust staff have perms or just rely on Admin
            # But "is_staff" logic implies we want Moderators to see it too.
            # Ideally we find a "Moderator" role or just rely on anyone with perms being able to see hidden channels?
            # Discord perms are tricky. Admins see everything. Mods with "View Channel" need specific overwrites if @everyone is denied.
            # Simplified: We create it, and setup command user (Admin) can configure specific role access if needed, 
            # Or we iterate roles and add any with Administrator/Kick/Ban? That's too message heavy.
            # Let's just create it private.
            
            active_cat = await guild.create_category("Tickets", overwrites=active_overwrites)
            
            # Archive: Read Only for all (who can see it)
            archive_overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
            }
            archive_cat = await guild.create_category("Archived Tickets", overwrites=archive_overwrites)
            
            # 2. Create Panel Channel (Public, Read-Only)
            panel_overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            panel_channel = await guild.create_text_channel("support-tickets", category=None, overwrites=panel_overwrites)
            
            # 3. Send Panel Message
            embed = discord.Embed(title="Support Tickets", description="Click the button below to open a ticket with staff.", color=discord.Color.blue())
            await panel_channel.send(embed=embed, view=TicketPanelView(self.bot))
            
            # 4. Save to DB
            self.bot.db.execute("INSERT OR REPLACE INTO ticket_settings (guild_id, active_category_id, archive_category_id, panel_channel_id) VALUES (?, ?, ?, ?)",
                                (guild.id, active_cat.id, archive_cat.id, panel_channel.id))
            
            await interaction.followup.send(f"Setup complete!\nPanel: {panel_channel.mention}\nActive Category: {active_cat.name}\nArchive Category: {archive_cat.name}\n\n**Note**: Please adjust category permissions to ensure your Staff roles can view the 'Tickets' category.")
            
        except Exception as e:
            await interaction.followup.send(f"Setup failed: {e}")

    @app_commands.command(name="ticket_add", description="Add a user to the ticket")
    @app_commands.describe(user="User to add")
    async def ticket_add(self, interaction: discord.Interaction, user: discord.Member):
        if "ticket-" not in interaction.channel.name:
             return await interaction.response.send_message("This does not look like a ticket channel.", ephemeral=True)
             
        # Check permissions (Owner or Staff)

        await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
        await interaction.response.send_message(f"Added {user.mention} to the ticket.")

    @app_commands.command(name="ticket_remove", description="Remove a user from the ticket")
    @app_commands.describe(user="User to remove")
    async def ticket_remove(self, interaction: discord.Interaction, user: discord.Member):
        if "ticket-" not in interaction.channel.name:
             return await interaction.response.send_message("This does not look like a ticket channel.", ephemeral=True)
        
        await interaction.channel.set_permissions(user, overwrite=None)
        await interaction.response.send_message(f"Removed {user.mention} from the ticket.")

async def setup(bot):
    await bot.add_cog(Tickets(bot))
