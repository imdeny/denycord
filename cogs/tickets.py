import discord
from discord.ext import commands
from discord import app_commands
import datetime
import asyncio
import chat_exporter
import io

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
            # Permissions: Everyone NO, User YES, Staff YES
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
            }
            
            try:
                # Increment ticket count
                self.bot.db.execute("UPDATE ticket_settings SET ticket_count = ticket_count + 1 WHERE guild_id = ?", (interaction.guild.id,))
                
                # Fetch new count
                count_data = self.bot.db.fetchone("SELECT ticket_count FROM ticket_settings WHERE guild_id = ?", (interaction.guild.id,))
                ticket_id = count_data[0] if count_data else 1 # Fallback to 1 if something weird happens
                
                channel_name = f"ticket-{ticket_id:04d}-{interaction.user.name}"
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

    async def generate_text_transcript(self, channel):
        output = io.StringIO()
        output.write(f"Transcript for {channel.name}\nServer: {channel.guild.name}\nGenerated: {datetime.datetime.now()}\n\n")
        
        async for msg in channel.history(limit=None, oldest_first=True):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            output.write(f"[{timestamp}] {msg.author}: {msg.clean_content}\n")
            if msg.attachments:
                for att in msg.attachments:
                     output.write(f"    [Attachment: {att.url}]\n")
            if msg.embeds:
                output.write(f"    [Embed: See HTML version]\n")
                
        return output.getvalue()

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="ticket_close", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        channel = interaction.channel
        guild = interaction.guild

        # Get settings for log channel
        settings = self.bot.db.fetchone("SELECT transcript_channel_id FROM ticket_settings WHERE guild_id = ?", (guild.id,))
        log_channel_id = settings[0] if settings else None
        log_channel = guild.get_channel(log_channel_id) if log_channel_id else None

        await channel.send("🔒 Generating transcript and closing ticket...")

        try:
            # Generate Transcripts
            html_transcript = await chat_exporter.export(channel)
            text_transcript = await self.generate_text_transcript(channel)
            
            if html_transcript is None:
                 await channel.send("Failed to generate transcript.")
                 return

            files = [
                discord.File(io.BytesIO(text_transcript.encode()), filename=f"transcript-{channel.name}.txt"),
                discord.File(io.BytesIO(html_transcript.encode()), filename=f"transcript-{channel.name}.html")
            ]

            # --- Send to Log Channel ---
            if log_channel:
                log_embed = discord.Embed(title="Ticket Closed", color=discord.Color.red(), timestamp=datetime.datetime.now())
                log_embed.add_field(name="Ticket", value=channel.name, inline=True)
                log_embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="Formats", value="📄 Text (Quick View)\n🌐 HTML (Full View - Download)", inline=False)
                
                # Fetch owner from DB to mention them if possible
                ticket_data = self.bot.db.fetchone("SELECT owner_id FROM tickets WHERE channel_id = ?", (channel.id,))
                owner_id = ticket_data[0] if ticket_data else None
                owner = guild.get_member(owner_id) if owner_id else None
                
                if owner:
                    log_embed.add_field(name="Owner", value=owner.mention, inline=True)
                
                # Reset pointers for file reuse? No, discord.File consumes the IO. Need fresh streams or list comprehension again.
                # Actually safest to just create new IO objects since encode() is cheap.
                log_files = [
                    discord.File(io.BytesIO(text_transcript.encode()), filename=f"transcript-{channel.name}.txt"),
                    discord.File(io.BytesIO(html_transcript.encode()), filename=f"transcript-{channel.name}.html")
                ]
                await log_channel.send(embed=log_embed, files=log_files)
            
            # --- Send to User (DM) ---
            if owner:
                 try:
                     dm_files = [
                        discord.File(io.BytesIO(text_transcript.encode()), filename=f"transcript-{channel.name}.txt"),
                        discord.File(io.BytesIO(html_transcript.encode()), filename=f"transcript-{channel.name}.html")
                    ]
                     await owner.send(
                         f"Your ticket **{channel.name}** has been closed.\n"
                         f"📄 **.txt**: Quick text view.\n"
                         f"🌐 **.html**: Download to view full chat with images/colors.", 
                         files=dm_files
                    )
                 except discord.Forbidden:
                     pass # User has DMs blocked

            # Close/Delete Ticket
            self.bot.db.execute("UPDATE tickets SET status = 'CLOSED' WHERE channel_id = ?", (channel.id,))
            
            await asyncio.sleep(5) # Give a moment to read the closing message
            await channel.delete(reason="Ticket Closed")

        except Exception as e:
            await channel.send(f"Error occurred while closing: {e}")

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
            # 1. Create Active Category
            active_overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
            }
            active_cat = await guild.create_category("Tickets", overwrites=active_overwrites)
            
            # 2. Create Log Channel (Private)
            log_overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            log_channel = await guild.create_text_channel("ticket-logs", overwrites=log_overwrites)
            
            # 3. Create Panel Channel (Public, Read-Only)
            panel_overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            panel_channel = await guild.create_text_channel("support-tickets", category=None, overwrites=panel_overwrites)
            
            # 4. Send Panel Message
            embed = discord.Embed(title="Support Tickets", description="Click the button below to open a ticket with staff.", color=discord.Color.blue())
            await panel_channel.send(embed=embed, view=TicketPanelView(self.bot))
            
            # 5. Save to DB
            self.bot.db.execute("INSERT OR REPLACE INTO ticket_settings (guild_id, active_category_id, panel_channel_id, transcript_channel_id) VALUES (?, ?, ?, ?)",
                                (guild.id, active_cat.id, panel_channel.id, log_channel.id))
            
            await interaction.followup.send(f"Setup complete!\nPanel: {panel_channel.mention}\nTickets Category: {active_cat.name}\nLogs Channel: {log_channel.mention}\n\n**Note**: Please adjust category permissions to ensure your Staff roles can view the 'Tickets' category and '#ticket-logs'.")
            
        except Exception as e:
            await interaction.followup.send(f"Setup failed: {e}")

    @app_commands.command(name="ticket_add", description="Add a user to the ticket")
    @app_commands.describe(user="User to add")
    async def ticket_add(self, interaction: discord.Interaction, user: discord.Member):
        if "ticket-" not in interaction.channel.name:
             return await interaction.response.send_message("This does not look like a ticket channel.", ephemeral=True)
             
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
