import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio

class VoiceControlView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.bot = cog.bot

    @discord.ui.button(label="Lock/Unlock", style=discord.ButtonStyle.secondary, custom_id="voice_lock_toggle", emoji="🔒")
    async def lock_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel:
            return await interaction.response.send_message("You are not in a voice channel.", ephemeral=True)
        
        if not channel.permissions_for(interaction.user).manage_channels:
             return await interaction.response.send_message("You don't have permission to manage this channel.", ephemeral=True)

        everyone_overwrite = channel.overwrites_for(interaction.guild.default_role)
        is_locked = everyone_overwrite.connect is False

        new_overwrites = channel.overwrites.copy()

        if is_locked:
            for target in new_overwrites:
                if isinstance(target, discord.Role):
                    new_overwrites[target].connect = None
            
            await channel.edit(overwrites=new_overwrites)
            await interaction.response.send_message("🔊 Channel **unlocked** (permissions reset to category default).", ephemeral=True)
        else:
            for target in new_overwrites:
                if isinstance(target, discord.Role):
                    new_overwrites[target].connect = False
            
            await channel.edit(overwrites=new_overwrites)
            await interaction.response.send_message("🔒 Channel **locked** for all roles.", ephemeral=True)

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.secondary, custom_id="voice_rename", emoji="✏️")
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel or not channel.permissions_for(interaction.user).manage_channels:
             return await interaction.response.send_message("You don't have permission or are not in a channel.", ephemeral=True)
        
        await interaction.response.send_modal(RenameModal(channel, self.cog))

    @discord.ui.button(label="Limit", style=discord.ButtonStyle.secondary, custom_id="voice_limit", emoji="👥")
    async def limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel or not channel.permissions_for(interaction.user).manage_channels:
             return await interaction.response.send_message("You don't have permission or are not in a channel.", ephemeral=True)
        
        await interaction.response.send_modal(LimitModal(channel))

    @discord.ui.button(label="Permit", style=discord.ButtonStyle.secondary, custom_id="voice_permit", emoji="✅")
    async def permit(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel or not channel.permissions_for(interaction.user).manage_channels:
             return await interaction.response.send_message("You don't have permission or are not in a channel.", ephemeral=True)
        
        await interaction.response.send_message("Select a user to permit:", view=PermitSelectView(channel), ephemeral=True)

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, custom_id="voice_kick", emoji="👢")
    async def kick(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel or not channel.permissions_for(interaction.user).manage_channels:
             return await interaction.response.send_message("You don't have permission or are not in a channel.", ephemeral=True)
        
        await interaction.response.send_message("Select a user to kick:", view=KickSelectView(channel), ephemeral=True)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success, custom_id="voice_claim", emoji="👑")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel:
             return await interaction.response.send_message("You are not in a voice channel.", ephemeral=True)
             
        active_owners = [m for m in channel.members if channel.permissions_for(m).manage_channels]
        
        if active_owners:
             return await interaction.response.send_message(f"This channel is already owned by {active_owners[0].mention}.", ephemeral=True)
             
        await channel.set_permissions(interaction.user, manage_channels=True, move_members=True, connect=True)
        await interaction.response.send_message(f"👑 You have claimed ownership of this channel!")

class RenameModal(discord.ui.Modal, title="Rename Channel"):
    name = discord.ui.TextInput(label="New Channel Name", placeholder="Enter new name...", min_length=1, max_length=100)

    def __init__(self, channel, cog):
        super().__init__()
        self.channel = channel
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await self.channel.edit(name=self.name.value)
        
        # Save as persistent default
        self.cog.save_user_settings(interaction.user.id, self.name.value)
        
        await interaction.response.send_message(f"Channel renamed to **{self.name.value}** and saved as your default.", ephemeral=True)

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

class PermitSelect(discord.ui.UserSelect):
    def __init__(self, channel):
        super().__init__(placeholder="Select user to permit...", min_values=1, max_values=1)
        self.channel = channel

    async def callback(self, interaction: discord.Interaction):
        member = self.values[0]
        await self.channel.set_permissions(member, connect=True)
        await interaction.response.send_message(f"✅ {member.mention} has been permitted to join.", ephemeral=True)

class PermitSelectView(discord.ui.View):
    def __init__(self, channel):
        super().__init__()
        self.add_item(PermitSelect(channel))

class KickSelect(discord.ui.UserSelect):
    def __init__(self, channel):
        super().__init__(placeholder="Select user to kick...", min_values=1, max_values=1)
        self.channel = channel

    async def callback(self, interaction: discord.Interaction):
        member = self.values[0]
        if member in self.channel.members:
            await member.move_to(None)
        await self.channel.set_permissions(member, connect=False)
        await interaction.response.send_message(f"👢 {member.mention} has been kicked and blocked.", ephemeral=True)

class KickSelectView(discord.ui.View):
    def __init__(self, channel):
        super().__init__()
        self.add_item(KickSelect(channel))

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temp_channels = [] # List of temp channel IDs to track for deletion
        # Caches
        self.hub_cache = {} 
        self.user_settings_cache = {}

    def get_hub_id(self, guild_id):
        if guild_id in self.hub_cache:
            return self.hub_cache[guild_id]
        
        result = self.bot.db.fetchone("SELECT hub_id FROM voice_hubs WHERE guild_id = ?", (guild_id,))
        if result:
            self.hub_cache[guild_id] = result[0]
            return result[0]
        return None

    def get_user_settings(self, user_id):
        if user_id in self.user_settings_cache:
            return self.user_settings_cache[user_id]
        
        result = self.bot.db.fetchone("SELECT name FROM voice_user_settings WHERE user_id = ?", (user_id,))
        if result:
            self.user_settings_cache[user_id] = result[0]
            return result[0]
        return None

    def save_user_settings(self, user_id, name):
        self.bot.db.execute("INSERT OR REPLACE INTO voice_user_settings (user_id, name) VALUES (?, ?)", (user_id, name))
        self.user_settings_cache[user_id] = name

    @app_commands.command(name="voice_setup", description="Setup the Join to Create channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = await guild.create_category("Voice Channels")
        channel = await guild.create_voice_channel("Join to Create", category=category)
        
        self.bot.db.execute("INSERT OR REPLACE INTO voice_hubs (guild_id, hub_id) VALUES (?, ?)", (guild.id, channel.id))
        self.hub_cache[guild.id] = channel.id
        
        await interaction.response.send_message(f"Setup complete! Join {channel.mention} to create a temporary voice channel.")

    @app_commands.command(name="voice_setname", description="Set your default temporary channel name")
    @app_commands.describe(name="The name for your channel (use {user} for your username)")
    async def setname(self, interaction: discord.Interaction, name: str):
        self.save_user_settings(interaction.user.id, name)
        await interaction.response.send_message(f"Your default channel name has been set to: `{name}`", ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        hub_id = self.get_hub_id(member.guild.id)
        if not hub_id:
            return

        # Join to Create Logic
        if after.channel and after.channel.id == hub_id:
            user_name = member.display_name
            user_config_name = self.get_user_settings(member.id)
            
            if user_config_name:
                channel_name = user_config_name.replace("{user}", user_name)
            else:
                channel_name = f"{user_name}'s Channel"

            category = after.channel.category
            overwrites = category.overwrites.copy() if category else {}
            overwrites[member] = discord.PermissionOverwrite(manage_channels=True, move_members=True, connect=True)
            
            try:
                new_channel = await member.guild.create_voice_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites
                )
                self.temp_channels.append(new_channel.id)
                await member.move_to(new_channel)
                
                embed = discord.Embed(
                    title="Voice Control Panel",
                    description=f"Welcome to your temporary channel, {member.mention}!\nUse the buttons below to manage your channel.",
                    color=discord.Color.blue()
                )
                view = VoiceControlView(self)
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
                    if before.channel.id in self.temp_channels:
                        self.temp_channels.remove(before.channel.id)

async def setup(bot):
    await bot.add_cog(Voice(bot))
