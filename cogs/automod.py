import discord
from discord.ext import commands
from discord import app_commands
import re
import json
import os

class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Cache: guild_id -> settings_dict
        self.settings_cache = {}
        
        # Load default bad words into memory if needed, 
        # but we relying on DB now.
        # We can implement a migration check if we want, but for now we assume fresh start or manual migration.

    def get_settings(self, guild_id):
        # Check cache first
        if guild_id in self.settings_cache:
            return self.settings_cache[guild_id]
            
        result = self.bot.db.fetchone("SELECT * FROM automod_settings WHERE guild_id = ?", (guild_id,))
        
        if result:
            settings = {
                "bad_words": result[1].split(",") if result[1] else [],
                "anti_invite": bool(result[2]),
                "anti_links": bool(result[3]),
                "anti_caps": bool(result[4]),
                "max_mentions": result[5],
                "max_emojis": result[6],
                "exempt_roles": [int(r) for r in result[7].split(",") if r] if result[7] else []
            }
        else:
            # Default settings
            settings = {
                "bad_words": [],
                "anti_invite": True,
                "anti_links": False,
                "anti_caps": False,
                "max_mentions": 5,
                "max_emojis": 5,
                "exempt_roles": []
            }
        
        # Update cache
        self.settings_cache[guild_id] = settings
        return settings

    def save_settings(self, guild_id, settings):
        bad_words_str = ",".join(settings["bad_words"])
        exempt_roles_str = ",".join(map(str, settings["exempt_roles"]))
        
        self.bot.db.execute('''INSERT OR REPLACE INTO automod_settings 
                     (guild_id, bad_words, anti_invite, anti_links, anti_caps, max_mentions, max_emojis, exempt_roles)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (guild_id, bad_words_str, int(settings["anti_invite"]), int(settings["anti_links"]), 
                   int(settings["anti_caps"]), settings["max_mentions"], settings["max_emojis"], exempt_roles_str))
        
        # Update cache
        self.settings_cache[guild_id] = settings

    async def check_exemption(self, message, settings):
        if message.author.guild_permissions.administrator:
            return True
        
        for role in message.author.roles:
            if role.id in settings["exempt_roles"]:
                return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return

        settings = self.get_settings(message.guild.id)
        
        if await self.check_exemption(message, settings):
            return

        content = message.content.lower()

        # 1. Anti-Invite
        if settings["anti_invite"]:
            if re.search(r"(discord.gg/|discord.com/invite/)", content):
                await message.delete()
                await message.channel.send(f"{message.author.mention}, invite links are not allowed!", delete_after=5)
                return

        # 2. Anti-Link
        if settings["anti_links"]:
            if re.search(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", content):
                 await message.delete()
                 await message.channel.send(f"{message.author.mention}, links are not allowed!", delete_after=5)
                 return

        # 3. Bad Words
        if settings["bad_words"]:
            for word in settings["bad_words"]:
                if word in content:
                    await message.delete()
                    await message.channel.send(f"{message.author.mention}, that language is not allowed!", delete_after=5)
                    return

        # 4. Anti-Caps
        if settings["anti_caps"] and len(message.content) > 10:
            caps_count = sum(1 for c in message.content if c.isupper())
            if caps_count / len(message.content) > 0.7:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, please stop shouting!", delete_after=5)
                return

        # 5. Anti-Ping (Mass Mentions)
        if settings["max_mentions"] > 0:
            if len(message.mentions) > settings["max_mentions"]:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, too many mentions!", delete_after=5)
                return

        # 6. Anti-Emoji
        if settings["max_emojis"] > 0:
            custom_emojis = len(re.findall(r'<a?:[^:]+:[0-9]+>', message.content))
            unicode_emojis = len(re.findall(r'[\U0001f600-\U0001f64f]', message.content))
            
            total_emojis = custom_emojis + unicode_emojis
            if total_emojis > settings["max_emojis"]:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, too many emojis!", delete_after=5)
                return

    # --- Commands ---

    @app_commands.command(name="automod_setup", description="Interactive setup for Auto-Moderation")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🛡️ Auto-Moderation Setup", color=discord.Color.blue())
        embed.description = "Use the following commands to configure AutoMod:\n\n" \
                            "• `/automod toggle <feature>` - Enable/Disable filters\n" \
                            "• `/automod limits <feature> <number>` - Set numeric limits\n" \
                            "• `/automod badwords <action> <word>` - Manage bad words\n" \
                            "• `/automod exempt <action> <role>` - Manage exempt roles"
        
        settings = self.get_settings(interaction.guild.id)
        status = f"**Anti-Invite:** {'✅' if settings['anti_invite'] else '❌'}\n" \
                 f"**Anti-Link:** {'✅' if settings['anti_links'] else '❌'}\n" \
                 f"**Anti-Caps:** {'✅' if settings['anti_caps'] else '❌'}\n" \
                 f"**Max Mentions:** {settings['max_mentions']}\n" \
                 f"**Max Emojis:** {settings['max_emojis']}\n" \
                 f"**Bad Words:** {len(settings['bad_words'])} words\n" \
                 f"**Exempt Roles:** {len(settings['exempt_roles'])} roles"
                 
        embed.add_field(name="Current Configuration", value=status, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="automod_toggle", description="Toggle boolean AutoMod features")
    @app_commands.describe(feature="The feature to toggle")
    @app_commands.choices(feature=[
        app_commands.Choice(name="Anti-Invite", value="anti_invite"),
        app_commands.Choice(name="Anti-Links", value="anti_links"),
        app_commands.Choice(name="Anti-Caps", value="anti_caps")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def toggle(self, interaction: discord.Interaction, feature: app_commands.Choice[str]):
        settings = self.get_settings(interaction.guild.id)
        current_val = settings[feature.value]
        settings[feature.value] = not current_val
        self.save_settings(interaction.guild.id, settings)
        
        status = "enabled" if not current_val else "disabled"
        await interaction.response.send_message(f"✅ **{feature.name}** has been **{status}**.")

    @app_commands.command(name="automod_limits", description="Set numeric limits for Mentions/Emojis")
    @app_commands.describe(feature="The feature to limit", limit="The max allowed (0 to disable)")
    @app_commands.choices(feature=[
        app_commands.Choice(name="Max Mentions", value="max_mentions"),
        app_commands.Choice(name="Max Emojis", value="max_emojis")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def limits(self, interaction: discord.Interaction, feature: app_commands.Choice[str], limit: int):
        if limit < 0:
            return await interaction.response.send_message("Limit cannot be negative.", ephemeral=True)
            
        settings = self.get_settings(interaction.guild.id)
        settings[feature.value] = limit
        self.save_settings(interaction.guild.id, settings)
        
        await interaction.response.send_message(f"✅ **{feature.name}** limit set to **{limit}**.")

    @app_commands.command(name="automod_badwords", description="Manage banned words")
    @app_commands.describe(action="Add, Remove, or List words", word="The word to add/remove")
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Remove", value="remove"),
        app_commands.Choice(name="List", value="list")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def badwords(self, interaction: discord.Interaction, action: app_commands.Choice[str], word: str = None):
        settings = self.get_settings(interaction.guild.id)
        
        if action.value == "list":
            if not settings["bad_words"]:
                return await interaction.response.send_message("No bad words configured.", ephemeral=True)
            return await interaction.response.send_message(f"🚫 **Banned Words:** {', '.join(settings['bad_words'])}", ephemeral=True)
        
        if not word:
            return await interaction.response.send_message("Please specify a word.", ephemeral=True)
        
        word = word.lower().strip()
        
        if action.value == "add":
            if word in settings["bad_words"]:
                return await interaction.response.send_message(f"'{word}' is already in the list.", ephemeral=True)
            settings["bad_words"].append(word)
            self.save_settings(interaction.guild.id, settings)
            await interaction.response.send_message(f"✅ Added **'{word}'** to banned words.")
            
        elif action.value == "remove":
            if word not in settings["bad_words"]:
                return await interaction.response.send_message(f"'{word}' is not in the list.", ephemeral=True)
            settings["bad_words"].remove(word)
            self.save_settings(interaction.guild.id, settings)
            await interaction.response.send_message(f"✅ Removed **'{word}'** from banned words.")

    @app_commands.command(name="automod_exempt", description="Manage exempt roles")
    @app_commands.describe(action="Add or Remove a role", role="The role to exempt")
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Remove", value="remove"),
        app_commands.Choice(name="List", value="list")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def exempt(self, interaction: discord.Interaction, action: app_commands.Choice[str], role: discord.Role = None):
        settings = self.get_settings(interaction.guild.id)
        
        if action.value == "list":
            if not settings["exempt_roles"]:
                return await interaction.response.send_message("No roles are exempt.", ephemeral=True)
            
            roles = [interaction.guild.get_role(rid).mention for rid in settings["exempt_roles"] if interaction.guild.get_role(rid)]
            return await interaction.response.send_message(f"🛡️ **Exempt Roles:** {', '.join(roles)}", ephemeral=True)

        if not role:
            return await interaction.response.send_message("Please specify a role.", ephemeral=True)
            
        if action.value == "add":
            if role.id in settings["exempt_roles"]:
                return await interaction.response.send_message("Role is already exempt.", ephemeral=True)
            settings["exempt_roles"].append(role.id)
            self.save_settings(interaction.guild.id, settings)
            await interaction.response.send_message(f"✅ Exempted {role.mention} from AutoMod.")
            
        elif action.value == "remove":
            if role.id not in settings["exempt_roles"]:
                return await interaction.response.send_message("Role is not exempt.", ephemeral=True)
            settings["exempt_roles"].remove(role.id)
            self.save_settings(interaction.guild.id, settings)
            await interaction.response.send_message(f"✅ Removed exemption for {role.mention}.")

async def setup(bot):
    await bot.add_cog(AutoMod(bot))
