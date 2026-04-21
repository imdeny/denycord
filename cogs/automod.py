import discord
from discord.ext import commands
from discord import app_commands
import re
import json
import time
import datetime
from collections import deque, defaultdict


class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings_cache = {}

        # Spam tracking: {guild_id: {user_id: deque of timestamps}}
        self.spam_tracker = defaultdict(lambda: defaultdict(deque))

        # Repeat message tracking: {guild_id: {user_id: {"msg": str, "count": int}}}
        self.repeat_tracker = defaultdict(lambda: defaultdict(dict))

        # Violation count tracking: {guild_id: {user_id: int}}
        self.violation_counts = defaultdict(lambda: defaultdict(int))

        # Raid tracking: {guild_id: deque of join timestamps}
        self.raid_tracker = defaultdict(deque)

        # Active raid lockdown state: {guild_id: bool}
        self.raid_lockdown = {}

    # -------------------------------------------------------------------------
    # Settings
    # -------------------------------------------------------------------------

    def _default_punishments(self):
        return [
            {"threshold": 1, "action": "delete", "duration": 0},
            {"threshold": 3, "action": "timeout", "duration": 300},
            {"threshold": 5, "action": "kick", "duration": 0},
        ]

    def _default_settings(self):
        return {
            "bad_words": [],
            "anti_invite": True,
            "anti_links": False,
            "anti_caps": False,
            "max_mentions": 5,
            "max_emojis": 5,
            "exempt_roles": [],
            "log_channel_id": None,
            "anti_spam": False,
            "spam_count": 5,
            "spam_seconds": 5,
            "min_account_age": 0,
            "anti_raid": False,
            "raid_count": 10,
            "raid_seconds": 10,
            "anti_repeat": False,
            "repeat_count": 3,
            "punishments": self._default_punishments(),
            "exempt_channels": [],
        }

    def get_settings(self, guild_id):
        if guild_id in self.settings_cache:
            return self.settings_cache[guild_id]

        result = self.bot.db.fetchone(
            "SELECT * FROM automod_settings WHERE guild_id = ?", (guild_id,)
        )

        if result:
            def _get(idx, default):
                return result[idx] if len(result) > idx and result[idx] is not None else default

            settings = {
                "bad_words": result[1].split(",") if result[1] else [],
                "anti_invite": bool(result[2]),
                "anti_links": bool(result[3]),
                "anti_caps": bool(result[4]),
                "max_mentions": result[5],
                "max_emojis": result[6],
                "exempt_roles": [int(r) for r in result[7].split(",") if r] if result[7] else [],
                "log_channel_id": _get(8, None),
                "anti_spam": bool(_get(9, 0)),
                "spam_count": _get(10, 5),
                "spam_seconds": _get(11, 5),
                "min_account_age": _get(12, 0),
                "anti_raid": bool(_get(13, 0)),
                "raid_count": _get(14, 10),
                "raid_seconds": _get(15, 10),
                "anti_repeat": bool(_get(16, 0)),
                "repeat_count": _get(17, 3),
                "punishments": json.loads(_get(18, None) or "null") or self._default_punishments(),
                "exempt_channels": [int(c) for c in _get(19, "").split(",") if c],
            }
        else:
            settings = self._default_settings()

        self.settings_cache[guild_id] = settings
        return settings

    def save_settings(self, guild_id, settings):
        self.bot.db.execute(
            '''INSERT OR REPLACE INTO automod_settings
               (guild_id, bad_words, anti_invite, anti_links, anti_caps,
                max_mentions, max_emojis, exempt_roles,
                log_channel_id, anti_spam, spam_count, spam_seconds,
                min_account_age, anti_raid, raid_count, raid_seconds,
                anti_repeat, repeat_count, punishments, exempt_channels)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (
                guild_id,
                ",".join(settings["bad_words"]),
                int(settings["anti_invite"]),
                int(settings["anti_links"]),
                int(settings["anti_caps"]),
                settings["max_mentions"],
                settings["max_emojis"],
                ",".join(map(str, settings["exempt_roles"])),
                settings.get("log_channel_id"),
                int(settings.get("anti_spam", False)),
                settings.get("spam_count", 5),
                settings.get("spam_seconds", 5),
                settings.get("min_account_age", 0),
                int(settings.get("anti_raid", False)),
                settings.get("raid_count", 10),
                settings.get("raid_seconds", 10),
                int(settings.get("anti_repeat", False)),
                settings.get("repeat_count", 3),
                json.dumps(settings.get("punishments", self._default_punishments())),
                ",".join(map(str, settings.get("exempt_channels", []))),
            ),
        )
        self.settings_cache[guild_id] = settings

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    async def is_exempt(self, message, settings):
        if message.author.guild_permissions.administrator:
            return True
        for role in message.author.roles:
            if role.id in settings["exempt_roles"]:
                return True
        if message.channel.id in settings.get("exempt_channels", []):
            return True
        return False

    async def send_log(self, guild, settings, title, user, reason, message=None):
        log_channel_id = settings.get("log_channel_id")
        if not log_channel_id:
            return
        channel = guild.get_channel(log_channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title=f"🛡️ AutoMod — {title}",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="Action", value=title, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        if message:
            content = (message.content[:500] if message.content else "*no content*")
            embed.add_field(name="Message", value=f"```{content}```", inline=False)
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    async def punish(self, message, settings, reason):
        """Increment violation count, apply the correct escalating punishment, and log it."""
        guild_id = message.guild.id
        user_id = message.author.id
        member = message.author

        self.violation_counts[guild_id][user_id] += 1
        count = self.violation_counts[guild_id][user_id]

        punishments = settings.get("punishments", self._default_punishments())

        # Pick the highest punishment whose threshold has been reached
        action_entry = {"action": "delete", "duration": 0}
        for p in sorted(punishments, key=lambda x: x["threshold"]):
            if count >= p["threshold"]:
                action_entry = p

        action = action_entry["action"]
        duration = action_entry.get("duration", 0)

        # Always attempt to delete the offending message
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        if action == "timeout" and duration > 0:
            try:
                until = discord.utils.utcnow() + datetime.timedelta(seconds=duration)
                await member.timeout(until, reason=f"AutoMod: {reason}")
                await message.channel.send(
                    f"{member.mention} has been timed out for **{duration // 60} minute(s)**. Reason: {reason}",
                    delete_after=8,
                )
            except discord.Forbidden:
                pass

        elif action == "kick":
            try:
                await message.channel.send(
                    f"**{member.name}** was kicked by AutoMod. Reason: {reason}",
                    delete_after=8,
                )
                await member.kick(reason=f"AutoMod: {reason}")
            except discord.Forbidden:
                pass

        elif action == "ban":
            try:
                await message.channel.send(
                    f"**{member.name}** was banned by AutoMod. Reason: {reason}",
                    delete_after=8,
                )
                await member.ban(reason=f"AutoMod: {reason}", delete_message_days=1)
            except discord.Forbidden:
                pass

        else:
            await message.channel.send(
                f"{member.mention}, {reason}", delete_after=5
            )

        await self.send_log(message.guild, settings, action.title(), member, reason, message)

    # -------------------------------------------------------------------------
    # Event: on_message
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return

        settings = self.get_settings(message.guild.id)

        if await self.is_exempt(message, settings):
            return

        now = time.time()
        content = message.content.lower()

        # 1. Anti-Spam — rate limit messages per user
        if settings.get("anti_spam"):
            spam_count = settings.get("spam_count", 5)
            spam_window = settings.get("spam_seconds", 5)

            dq = self.spam_tracker[message.guild.id][message.author.id]
            dq.append(now)
            while dq and dq[0] < now - spam_window:
                dq.popleft()

            if len(dq) >= spam_count:
                dq.clear()
                await self.punish(message, settings, "Sending messages too fast")
                return

        # 2. Repeat Message Detection
        if settings.get("anti_repeat"):
            repeat_limit = settings.get("repeat_count", 3)
            uid = message.author.id
            gid = message.guild.id
            stripped = message.content.strip().lower()

            tracker = self.repeat_tracker[gid][uid]
            if tracker.get("msg") == stripped:
                tracker["count"] = tracker.get("count", 1) + 1
                if tracker["count"] >= repeat_limit:
                    tracker["count"] = 0
                    await self.punish(message, settings, "Repeated the same message too many times")
                    return
            else:
                tracker["msg"] = stripped
                tracker["count"] = 1

        # 3. Anti-Invite
        if settings["anti_invite"]:
            if re.search(r"discord\.gg/|discord\.com/invite/", content):
                await self.punish(message, settings, "Posting invite links is not allowed")
                return

        # 4. Anti-Link
        if settings["anti_links"]:
            if re.search(r"https?://[^\s]+", content):
                await self.punish(message, settings, "Posting links is not allowed")
                return

        # 5. Bad Words — word boundary matching to avoid false positives
        if settings["bad_words"]:
            for word in settings["bad_words"]:
                if re.search(r"\b" + re.escape(word) + r"\b", content):
                    await self.punish(message, settings, "Message contained a banned word")
                    return

        # 6. Anti-Caps — checks letter ratio, not total character ratio
        if settings["anti_caps"] and len(message.content) > 10:
            letters = [c for c in message.content if c.isalpha()]
            if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.7:
                await self.punish(message, settings, "Excessive use of capital letters")
                return

        # 7. Mass Mentions
        if settings["max_mentions"] > 0:
            if len(message.mentions) > settings["max_mentions"]:
                await self.punish(
                    message, settings,
                    f"Too many mentions (max {settings['max_mentions']})"
                )
                return

        # 8. Emoji Spam
        if settings["max_emojis"] > 0:
            custom = len(re.findall(r"<a?:[^:]+:[0-9]+>", message.content))
            unicode = len(re.findall(r"[\U0001f300-\U0001faff]", message.content))
            if custom + unicode > settings["max_emojis"]:
                await self.punish(
                    message, settings,
                    f"Too many emojis (max {settings['max_emojis']})"
                )
                return

    # -------------------------------------------------------------------------
    # Event: on_member_join
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member):
        settings = self.get_settings(member.guild.id)
        now = time.time()

        # Anti-Raid — detect mass joins in a short window
        if settings.get("anti_raid"):
            raid_count = settings.get("raid_count", 10)
            raid_seconds = settings.get("raid_seconds", 10)

            dq = self.raid_tracker[member.guild.id]
            dq.append(now)
            while dq and dq[0] < now - raid_seconds:
                dq.popleft()

            if len(dq) >= raid_count and not self.raid_lockdown.get(member.guild.id):
                self.raid_lockdown[member.guild.id] = True
                await self._trigger_lockdown(member.guild, settings, len(dq), raid_seconds)

        # New Account Filter
        min_age = settings.get("min_account_age", 0)
        if min_age > 0:
            account_age_days = (discord.utils.utcnow() - member.created_at).days
            if account_age_days < min_age:
                try:
                    await member.send(
                        f"You were kicked from **{member.guild.name}** because your account is too new. "
                        f"Accounts must be at least **{min_age} day(s)** old to join."
                    )
                except discord.Forbidden:
                    pass
                try:
                    await member.kick(
                        reason=f"AutoMod: Account too new ({account_age_days}d old, minimum {min_age}d)"
                    )
                except discord.Forbidden:
                    pass
                await self.send_log(
                    member.guild, settings,
                    "Kicked (New Account)", member,
                    f"Account is {account_age_days} day(s) old (minimum: {min_age})"
                )

    async def _trigger_lockdown(self, guild, settings, join_count, window_seconds):
        """Lock all text channels and alert the log channel."""
        locked = 0
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.send_messages = False
                await channel.set_permissions(
                    guild.default_role, overwrite=overwrite,
                    reason="AutoMod: Anti-raid lockdown"
                )
                locked += 1
            except discord.Forbidden:
                continue

        log_channel_id = settings.get("log_channel_id")
        if log_channel_id:
            channel = guild.get_channel(log_channel_id)
            if channel:
                embed = discord.Embed(
                    title="🚨 RAID DETECTED — Server Locked Down",
                    description=(
                        f"**{join_count}** members joined within **{window_seconds}** seconds.\n\n"
                        f"**{locked}** channels have been locked.\n\n"
                        f"Use `/automod_unlock` to lift the lockdown once the raid is over."
                    ),
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    @app_commands.command(name="automod_setup", description="View the current AutoMod configuration")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        settings = self.get_settings(interaction.guild.id)

        embed = discord.Embed(title="🛡️ AutoMod Configuration", color=discord.Color.blue())

        core = (
            f"Anti-Invite: {'✅' if settings['anti_invite'] else '❌'}\n"
            f"Anti-Link: {'✅' if settings['anti_links'] else '❌'}\n"
            f"Anti-Caps: {'✅' if settings['anti_caps'] else '❌'}\n"
            f"Max Mentions: {settings['max_mentions']}\n"
            f"Max Emojis: {settings['max_emojis']}\n"
            f"Bad Words: {len(settings['bad_words'])} words"
        )
        embed.add_field(name="Core Filters", value=core, inline=True)

        advanced = (
            f"Anti-Spam: {'✅' if settings.get('anti_spam') else '❌'} "
            f"({settings.get('spam_count', 5)} msgs / {settings.get('spam_seconds', 5)}s)\n"
            f"Anti-Repeat: {'✅' if settings.get('anti_repeat') else '❌'} "
            f"(x{settings.get('repeat_count', 3)})\n"
            f"Anti-Raid: {'✅' if settings.get('anti_raid') else '❌'} "
            f"({settings.get('raid_count', 10)} joins / {settings.get('raid_seconds', 10)}s)\n"
            f"Min Account Age: {settings.get('min_account_age', 0)} days"
        )
        embed.add_field(name="Advanced Filters", value=advanced, inline=True)

        punishments = settings.get("punishments", self._default_punishments())
        pun_lines = []
        for p in sorted(punishments, key=lambda x: x["threshold"]):
            dur = f" ({p['duration'] // 60}m)" if p.get("duration") else ""
            pun_lines.append(f"Violation #{p['threshold']}: **{p['action'].title()}**{dur}")
        embed.add_field(name="Punishment Ladder", value="\n".join(pun_lines) or "None set", inline=False)

        log_ch = interaction.guild.get_channel(settings.get("log_channel_id") or 0)
        embed.add_field(name="Log Channel", value=log_ch.mention if log_ch else "Not set", inline=True)
        embed.add_field(name="Exempt Roles", value=str(len(settings["exempt_roles"])), inline=True)
        embed.add_field(name="Exempt Channels", value=str(len(settings.get("exempt_channels", []))), inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="automod_toggle", description="Toggle an AutoMod filter on or off")
    @app_commands.describe(feature="The filter to toggle")
    @app_commands.choices(feature=[
        app_commands.Choice(name="Anti-Invite", value="anti_invite"),
        app_commands.Choice(name="Anti-Links", value="anti_links"),
        app_commands.Choice(name="Anti-Caps", value="anti_caps"),
        app_commands.Choice(name="Anti-Spam", value="anti_spam"),
        app_commands.Choice(name="Anti-Repeat Messages", value="anti_repeat"),
        app_commands.Choice(name="Anti-Raid", value="anti_raid"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def toggle(self, interaction: discord.Interaction, feature: app_commands.Choice[str]):
        settings = self.get_settings(interaction.guild.id)
        current = settings.get(feature.value, False)
        settings[feature.value] = not current
        self.save_settings(interaction.guild.id, settings)
        status = "enabled" if not current else "disabled"
        await interaction.response.send_message(f"✅ **{feature.name}** has been **{status}**.")

    @app_commands.command(name="automod_limits", description="Set numeric limits for AutoMod features")
    @app_commands.describe(feature="The setting to configure", limit="The value to set")
    @app_commands.choices(feature=[
        app_commands.Choice(name="Max Mentions", value="max_mentions"),
        app_commands.Choice(name="Max Emojis", value="max_emojis"),
        app_commands.Choice(name="Spam: Messages per window", value="spam_count"),
        app_commands.Choice(name="Spam: Window (seconds)", value="spam_seconds"),
        app_commands.Choice(name="Repeat: Same message count", value="repeat_count"),
        app_commands.Choice(name="Raid: Joins per window", value="raid_count"),
        app_commands.Choice(name="Raid: Window (seconds)", value="raid_seconds"),
        app_commands.Choice(name="Min Account Age (days)", value="min_account_age"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def limits(self, interaction: discord.Interaction, feature: app_commands.Choice[str], limit: int):
        if limit < 0:
            return await interaction.response.send_message("Limit cannot be negative.", ephemeral=True)
        settings = self.get_settings(interaction.guild.id)
        settings[feature.value] = limit
        self.save_settings(interaction.guild.id, settings)
        await interaction.response.send_message(f"✅ **{feature.name}** set to **{limit}**.")

    @app_commands.command(name="automod_logchannel", description="Set the channel where AutoMod actions are logged")
    @app_commands.describe(channel="The channel to log AutoMod actions to")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        settings = self.get_settings(interaction.guild.id)
        settings["log_channel_id"] = channel.id
        self.save_settings(interaction.guild.id, settings)
        await interaction.response.send_message(f"✅ AutoMod logs will be sent to {channel.mention}.")

    @app_commands.command(name="automod_punishment", description="Configure the punishment for a violation threshold")
    @app_commands.describe(
        threshold="Which violation number triggers this (e.g. 3 = 3rd offence)",
        action="What to do",
        duration_minutes="Timeout duration in minutes (timeout action only)",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Delete Only", value="delete"),
        app_commands.Choice(name="Timeout", value="timeout"),
        app_commands.Choice(name="Kick", value="kick"),
        app_commands.Choice(name="Ban", value="ban"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def set_punishment(
        self,
        interaction: discord.Interaction,
        threshold: int,
        action: app_commands.Choice[str],
        duration_minutes: int = 0,
    ):
        if threshold < 1:
            return await interaction.response.send_message("Threshold must be at least 1.", ephemeral=True)

        settings = self.get_settings(interaction.guild.id)
        punishments = [p for p in settings.get("punishments", self._default_punishments()) if p["threshold"] != threshold]
        punishments.append({"threshold": threshold, "action": action.value, "duration": duration_minutes * 60})
        punishments.sort(key=lambda x: x["threshold"])
        settings["punishments"] = punishments
        self.save_settings(interaction.guild.id, settings)

        dur_str = f" for {duration_minutes} minute(s)" if duration_minutes else ""
        await interaction.response.send_message(
            f"✅ Violation **#{threshold}** will result in **{action.name}**{dur_str}."
        )

    @app_commands.command(name="automod_badwords", description="Manage the banned word list")
    @app_commands.describe(action="Add, Remove, or List words", word="The word to add or remove")
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Remove", value="remove"),
        app_commands.Choice(name="List", value="list"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def badwords(self, interaction: discord.Interaction, action: app_commands.Choice[str], word: str = None):
        settings = self.get_settings(interaction.guild.id)

        if action.value == "list":
            if not settings["bad_words"]:
                return await interaction.response.send_message("No bad words configured.", ephemeral=True)
            return await interaction.response.send_message(
                f"🚫 **Banned Words ({len(settings['bad_words'])}):** {', '.join(settings['bad_words'])}",
                ephemeral=True,
            )

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

    @app_commands.command(name="automod_exempt", description="Manage roles that are exempt from AutoMod")
    @app_commands.describe(action="Add, Remove, or List exempt roles", role="The role to exempt")
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Remove", value="remove"),
        app_commands.Choice(name="List", value="list"),
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

    @app_commands.command(name="automod_exempt_channel", description="Exempt a channel from all AutoMod filters")
    @app_commands.describe(action="Add, Remove, or List exempt channels", channel="The channel to exempt")
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Remove", value="remove"),
        app_commands.Choice(name="List", value="list"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def exempt_channel(self, interaction: discord.Interaction, action: app_commands.Choice[str], channel: discord.TextChannel = None):
        settings = self.get_settings(interaction.guild.id)
        exempt = settings.get("exempt_channels", [])

        if action.value == "list":
            if not exempt:
                return await interaction.response.send_message("No channels are exempt.", ephemeral=True)
            channels = [interaction.guild.get_channel(cid).mention for cid in exempt if interaction.guild.get_channel(cid)]
            return await interaction.response.send_message(f"🛡️ **Exempt Channels:** {', '.join(channels)}", ephemeral=True)

        if not channel:
            return await interaction.response.send_message("Please specify a channel.", ephemeral=True)

        if action.value == "add":
            if channel.id in exempt:
                return await interaction.response.send_message("Channel is already exempt.", ephemeral=True)
            exempt.append(channel.id)
            settings["exempt_channels"] = exempt
            self.save_settings(interaction.guild.id, settings)
            await interaction.response.send_message(f"✅ {channel.mention} is now exempt from AutoMod.")

        elif action.value == "remove":
            if channel.id not in exempt:
                return await interaction.response.send_message("Channel is not exempt.", ephemeral=True)
            exempt.remove(channel.id)
            settings["exempt_channels"] = exempt
            self.save_settings(interaction.guild.id, settings)
            await interaction.response.send_message(f"✅ Removed AutoMod exemption for {channel.mention}.")

    @app_commands.command(name="automod_unlock", description="Lift an active raid lockdown and unlock all channels")
    @app_commands.checks.has_permissions(administrator=True)
    async def unlock(self, interaction: discord.Interaction):
        if not self.raid_lockdown.get(interaction.guild.id):
            return await interaction.response.send_message("There is no active lockdown.", ephemeral=True)

        await interaction.response.defer()

        unlocked = 0
        for channel in interaction.guild.text_channels:
            try:
                overwrite = channel.overwrites_for(interaction.guild.default_role)
                overwrite.send_messages = None
                await channel.set_permissions(
                    interaction.guild.default_role, overwrite=overwrite,
                    reason="AutoMod: Raid lockdown lifted"
                )
                unlocked += 1
            except discord.Forbidden:
                continue

        self.raid_lockdown[interaction.guild.id] = False
        self.raid_tracker[interaction.guild.id].clear()

        await interaction.followup.send(f"✅ Lockdown lifted. **{unlocked}** channels have been unlocked.")

    @app_commands.command(name="automod_violations", description="Check a user's current AutoMod violation count")
    @app_commands.describe(user="The user to check")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def check_violations(self, interaction: discord.Interaction, user: discord.Member):
        count = self.violation_counts[interaction.guild.id].get(user.id, 0)
        await interaction.response.send_message(
            f"🛡️ {user.mention} has **{count}** AutoMod violation(s) this session.",
            ephemeral=True,
        )

    @app_commands.command(name="automod_reset_violations", description="Reset a user's AutoMod violation count")
    @app_commands.describe(user="The user to reset")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_violations(self, interaction: discord.Interaction, user: discord.Member):
        self.violation_counts[interaction.guild.id][user.id] = 0
        await interaction.response.send_message(f"✅ Reset violation count for {user.mention}.")


async def setup(bot):
    await bot.add_cog(AutoMod(bot))