import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio

VOICE_CONFIG_FILE = "voice_config.json"

class VoiceControlView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Lock/Unlock", style=discord.ButtonStyle.secondary, custom_id="voice_lock_toggle", emoji="🔒")
    async def lock_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel:
            return await interaction.response.send_message("You are not in a voice channel.", ephemeral=True)
        
        # Check ownership (simple check: is the user the one who created it? 
        # For now, we assume the user in the channel with manage_channels permission is the owner, 
        # or we rely on the bot's tracking. Since we don't have persistent ownership tracking in this simple view,
        # we'll check if the user has permission to manage the channel or if they are the only one there initially.
        # A better way for this specific bot is to check if the channel is a temp channel and if the user is the 'owner'.
        # We can store ownership in the channel topic or just check permissions.)
        
        # Actually, for "Join to Create", usually the bot gives the user Manage Channel perms or specific perms.
        # Let's check if the user has "Manage Channel" permission on this channel.
        if not channel.permissions_for(interaction.user).manage_channels:
             return await interaction.response.send_message("You don't have permission to manage this channel.", ephemeral=True)

        # Toggle logic
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        if overwrite.connect is False:
            overwrite.connect = None # Reset to default (usually True/Neutral)
            await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
            await interaction.response.send_message("🔊 Channel **unlocked** for everyone.", ephemeral=True)
        else:
            overwrite.connect = False
            await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
            await interaction.response.send_message("🔒 Channel **locked**.", ephemeral=True)

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.secondary, custom_id="voice_rename", emoji="✏️")
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel or not channel.permissions_for(interaction.user).manage_channels:
             return await interaction.response.send_message("You don't have permission or are not in a channel.", ephemeral=True)
        
        await interaction.response.send_modal(RenameModal(channel))

    @discord.ui.button(label="Limit", style=discord.ButtonStyle.secondary, custom_id="voice_limit", emoji="👥")
    async def limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel or not channel.permissions_for(interaction.user).manage_channels:
             return await interaction.response.send_message("You don't have permission or are not in a channel.", ephemeral=True)
        
        await interaction.response.send_modal(LimitModal(channel))

class RenameModal(discord.ui.Modal, title="Rename Channel"):
    name = discord.ui.TextInput(label="New Channel Name", placeholder="Enter new name...", min_length=1, max_length=100)

    def __init__(self, channel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        await self.channel.edit(name=self.name.value)
        await interaction.response.send_message(f"Channel renamed to **{self.name.value}**", ephemeral=True)

class LimitModal(discord.ui.Modal, title="Set User Limit"):
    limit = discord.ui.TextInput(label="User Limit (0 for unlimited)", placeholder="Enter number...", min_length=1, max_length=2)

    def __init__(self, channel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit_val = int(self.limit.value)
            if limit_val < 0 or limit_val > 99:
                raise ValueError
            await self.channel.edit(user_limit=limit_val)
            await interaction.response.send_message(f"User limit set to **{limit_val}**", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Invalid number. Please enter a number between 0 and 99.", ephemeral=True)

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = self.load_config()
        self.temp_channels = [] # List of temp channel IDs to track for deletion

    def load_config(self):
        if not os.path.exists(VOICE_CONFIG_FILE):
            return {"guilds": {}, "user_settings": {}}
        try:
            with open(VOICE_CONFIG_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"guilds": {}, "user_settings": {}}

    def save_config(self):
        with open(VOICE_CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)

    @app_commands.command(name="voice_setup", description="Setup the Join to Create channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = await guild.create_category("Voice Channels")
        channel = await guild.create_voice_channel("Join to Create", category=category)
        
        if str(guild.id) not in self.config["guilds"]:
            self.config["guilds"][str(guild.id)] = {}
        
        self.config["guilds"][str(guild.id)]["hub_id"] = channel.id
        self.save_config()
        
        await interaction.response.send_message(f"Setup complete! Join {channel.mention} to create a temporary voice channel.")

    @app_commands.command(name="voice_setname", description="Set your default temporary channel name")
    @app_commands.describe(name="The name for your channel (use {user} for your username)")
    async def setname(self, interaction: discord.Interaction, name: str):
        user_id = str(interaction.user.id)
        if "user_settings" not in self.config:
            self.config["user_settings"] = {}
        if user_id not in self.config["user_settings"]:
            self.config["user_settings"][user_id] = {}
            
        self.config["user_settings"][user_id]["name"] = name
        self.save_config()
        await interaction.response.send_message(f"Your default channel name has been set to: `{name}`", ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild_id = str(member.guild.id)
        if guild_id not in self.config["guilds"]:
            return

        hub_id = self.config["guilds"][guild_id].get("hub_id")
        
        # Join to Create Logic
        if after.channel and after.channel.id == hub_id:
            # Determine channel name
            user_id = str(member.id)
            user_name = member.display_name
            
            if user_id in self.config.get("user_settings", {}) and "name" in self.config["user_settings"][user_id]:
                channel_name = self.config["user_settings"][user_id]["name"].replace("{user}", user_name)
            else:
                channel_name = f"{user_name}'s Channel"

            # Create channel
            category = after.channel.category
            # Inherit permissions from category
            overwrites = category.overwrites.copy() if category else {}
            # Add specific permissions for the creator
            overwrites[member] = discord.PermissionOverwrite(manage_channels=True, move_members=True, connect=True)
            
            try:
                new_channel = await member.guild.create_voice_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites
                )
                self.temp_channels.append(new_channel.id)
                
                # Move member
                await member.move_to(new_channel)
                
                # Send control panel
                embed = discord.Embed(
                    title="Voice Control Panel",
                    description=f"Welcome to your temporary channel, {member.mention}!\nUse the buttons below to manage your channel.",
                    color=discord.Color.blue()
                )
                view = VoiceControlView(self.bot)
                await new_channel.send(embed=embed, view=view)
                
            except Exception as e:
                print(f"Error creating voice channel: {e}")

        # Cleanup Logic
        if before.channel and before.channel.id in self.temp_channels:
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                    self.temp_channels.remove(before.channel.id)
                except Exception as e:
                    print(f"Error deleting channel: {e}")
                    # If delete fails (e.g. already deleted), just remove from list
                    if before.channel.id in self.temp_channels:
                        self.temp_channels.remove(before.channel.id)

async def setup(bot):
    await bot.add_cog(Voice(bot))
