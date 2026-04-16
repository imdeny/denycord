import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone
import json
import io
import os
import logging


class Backup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.logger = logging.getLogger("Backup")
        os.makedirs("backups", exist_ok=True)
        self.scheduled_backup_loop.start()

    def cog_unload(self):
        self.scheduled_backup_loop.cancel()

    # -------------------------------------------------------------------------
    # Backup builder
    # -------------------------------------------------------------------------

    async def _create_backup(self, guild: discord.Guild) -> dict:
        backup = {
            "meta": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "guild_id": guild.id,
                "guild_name": guild.name,
            },
            "server": {
                "name": guild.name,
                "description": guild.description,
                "verification_level": guild.verification_level.value,
                "default_notifications": guild.default_notifications.value,
                "explicit_content_filter": guild.explicit_content_filter.value,
                "afk_timeout": guild.afk_timeout,
                "afk_channel_name": guild.afk_channel.name if guild.afk_channel else None,
                "icon_url": str(guild.icon.url) if guild.icon else None,
            },
            "roles": [],
            "categories": [],
            "channels": [],
            "emojis": [],
            "bot_config": {},
            "member_levels": [],
            "warnings": [],
        }

        # Roles (skip @everyone)
        for role in sorted(guild.roles, key=lambda r: r.position):
            if role.is_default():
                continue
            backup["roles"].append({
                "id": role.id,
                "name": role.name,
                "color": role.color.value,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "permissions": role.permissions.value,
                "position": role.position,
            })

        def serialize_overwrites(channel):
            result = {}
            for target, overwrite in channel.overwrites.items():
                allow, deny = overwrite.pair()
                result[str(target.id)] = {
                    "type": "role" if isinstance(target, discord.Role) else "member",
                    "allow": allow.value,
                    "deny": deny.value,
                }
            return result

        # Categories
        for cat in sorted(guild.categories, key=lambda c: c.position):
            backup["categories"].append({
                "id": cat.id,
                "name": cat.name,
                "position": cat.position,
                "overwrites": serialize_overwrites(cat),
            })

        # Channels (all non-category)
        for channel in guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                continue
            ch_data = {
                "id": channel.id,
                "name": channel.name,
                "type": str(channel.type),
                "position": channel.position,
                "category_id": channel.category_id,
                "overwrites": serialize_overwrites(channel),
            }
            if isinstance(channel, discord.TextChannel):
                ch_data["topic"] = channel.topic
                ch_data["slowmode"] = channel.slowmode_delay
                ch_data["nsfw"] = channel.nsfw
            elif isinstance(channel, discord.VoiceChannel):
                ch_data["bitrate"] = channel.bitrate
                ch_data["user_limit"] = channel.user_limit
            backup["channels"].append(ch_data)

        # Emojis (name + URL for reference)
        for emoji in guild.emojis:
            backup["emojis"].append({"name": emoji.name, "url": str(emoji.url)})

        # Bot config — wrap each section in try/except so one bad table never breaks the whole backup
        guild_id = guild.id
        cfg = {}

        try:
            row = self.db.fetchone("SELECT channel_id, message_text FROM welcome_config WHERE guild_id = ?", (guild_id,))
            if row:
                cfg["welcome"] = {"channel_id": row[0], "message_text": row[1]}
        except Exception:
            pass

        try:
            rows = self.db.fetchall("SELECT role_id FROM auto_roles WHERE guild_id = ?", (guild_id,))
            cfg["auto_roles"] = [r[0] for r in rows]
        except Exception:
            pass

        try:
            row = self.db.fetchone(
                "SELECT active_category_id, archive_category_id, panel_channel_id, transcript_channel_id FROM ticket_settings WHERE guild_id = ?",
                (guild_id,),
            )
            if row:
                cfg["ticket_settings"] = {
                    "active_category_id": row[0],
                    "archive_category_id": row[1],
                    "panel_channel_id": row[2],
                    "transcript_channel_id": row[3],
                }
        except Exception:
            pass

        try:
            rows = self.db.fetchall("SELECT name, content FROM ticket_templates WHERE guild_id = ?", (guild_id,))
            cfg["ticket_templates"] = [{"name": r[0], "content": r[1]} for r in rows]
        except Exception:
            pass

        try:
            rows = self.db.fetchall("SELECT level, role_id FROM level_roles WHERE guild_id = ?", (guild_id,))
            cfg["level_roles"] = [{"level": r[0], "role_id": r[1]} for r in rows]
        except Exception:
            pass

        try:
            row = self.db.fetchone(
                "SELECT bad_words, anti_invite, anti_links, anti_caps, max_mentions, max_emojis, exempt_roles FROM automod_settings WHERE guild_id = ?",
                (guild_id,),
            )
            if row:
                cfg["automod"] = {
                    "bad_words": row[0], "anti_invite": row[1], "anti_links": row[2],
                    "anti_caps": row[3], "max_mentions": row[4], "max_emojis": row[5],
                    "exempt_roles": row[6],
                }
        except Exception:
            pass

        try:
            row = self.db.fetchone("SELECT warn_threshold, action, duration_minutes FROM automod_actions WHERE guild_id = ?", (guild_id,))
            if row:
                cfg["automod_actions"] = {"warn_threshold": row[0], "action": row[1], "duration_minutes": row[2]}
        except Exception:
            pass

        try:
            row = self.db.fetchone("SELECT channel_id FROM mod_logs WHERE guild_id = ?", (guild_id,))
            if row:
                cfg["mod_logs_channel_id"] = row[0]
        except Exception:
            pass

        try:
            rows = self.db.fetchall("SELECT stat_type, channel_id FROM stats_channels WHERE guild_id = ?", (guild_id,))
            cfg["stats_channels"] = [{"stat_type": r[0], "channel_id": r[1]} for r in rows]
        except Exception:
            pass

        try:
            row = self.db.fetchone("SELECT channel_id, role_id FROM birthday_settings WHERE guild_id = ?", (guild_id,))
            if row:
                cfg["birthday_settings"] = {"channel_id": row[0], "role_id": row[1]}
        except Exception:
            pass

        try:
            rows = self.db.fetchall("SELECT user_id, month, day FROM birthdays WHERE guild_id = ?", (guild_id,))
            cfg["birthdays"] = [{"user_id": r[0], "month": r[1], "day": r[2]} for r in rows]
        except Exception:
            pass

        try:
            row = self.db.fetchone("SELECT hub_id FROM voice_hubs WHERE guild_id = ?", (guild_id,))
            if row:
                cfg["voice_hub_id"] = row[0]
        except Exception:
            pass

        backup["bot_config"] = cfg

        # Member XP/levels
        try:
            rows = self.db.fetchall("SELECT user_id, xp, level FROM levels WHERE guild_id = ?", (guild_id,))
            backup["member_levels"] = [{"user_id": r[0], "xp": r[1], "level": r[2]} for r in rows]
        except Exception:
            pass

        # Warnings
        try:
            rows = self.db.fetchall(
                "SELECT user_id, moderator_id, reason, timestamp FROM warnings WHERE guild_id = ?", (guild_id,)
            )
            backup["warnings"] = [{"user_id": r[0], "moderator_id": r[1], "reason": r[2], "timestamp": str(r[3])} for r in rows]
        except Exception:
            pass

        return backup

    def _to_file(self, backup: dict, guild_name: str) -> tuple[discord.File, str]:
        data = json.dumps(backup, indent=2, ensure_ascii=False)
        buf = io.BytesIO(data.encode("utf-8"))
        buf.seek(0)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in guild_name)
        filename = f"backup_{safe_name}_{timestamp}.json"
        return discord.File(buf, filename=filename), filename

    def _save_locally(self, guild_id: int, backup: dict):
        path = os.path.join("backups", f"{guild_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(backup, f, indent=2, ensure_ascii=False)

    def _build_summary_embed(self, backup: dict, title: str, color: discord.Color) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=f"Server: **{backup['meta']['guild_name']}**\nCreated: {backup['meta']['created_at'][:10]}",
            color=color,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Roles", value=len(backup["roles"]), inline=True)
        embed.add_field(name="Categories", value=len(backup["categories"]), inline=True)
        embed.add_field(name="Channels", value=len(backup["channels"]), inline=True)
        embed.add_field(name="Emojis", value=len(backup["emojis"]), inline=True)
        embed.add_field(name="Members w/ XP", value=len(backup.get("member_levels", [])), inline=True)
        embed.add_field(name="Warnings", value=len(backup.get("warnings", [])), inline=True)
        return embed

    # -------------------------------------------------------------------------
    # Scheduled backup loop
    # -------------------------------------------------------------------------

    @tasks.loop(hours=1)
    async def scheduled_backup_loop(self):
        now = datetime.now(timezone.utc).timestamp()
        rows = self.db.fetchall(
            "SELECT guild_id, channel_id, interval_hours, last_backup_at FROM backup_settings "
            "WHERE channel_id IS NOT NULL AND interval_hours IS NOT NULL"
        )
        for guild_id, channel_id, interval_hours, last_backup_at in rows:
            if last_backup_at and (now - last_backup_at) < interval_hours * 3600:
                continue
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue
            channel = guild.get_channel(channel_id)
            if channel is None:
                continue
            try:
                backup = await self._create_backup(guild)
                self._save_locally(guild_id, backup)
                file, filename = self._to_file(backup, guild.name)
                embed = self._build_summary_embed(backup, "🗄️ Scheduled Backup", discord.Color.blurple())
                await channel.send(embed=embed, file=file)
                self.db.execute(
                    "UPDATE backup_settings SET last_backup_at = ? WHERE guild_id = ?",
                    (now, guild_id),
                )
            except Exception as e:
                print(f"[Backup] Scheduled backup failed for guild {guild_id}: {e}")

    @scheduled_backup_loop.before_loop
    async def before_scheduled_backup(self):
        await self.bot.wait_until_ready()

    # -------------------------------------------------------------------------
    # Restore helpers
    # -------------------------------------------------------------------------

    def _deserialize_overwrites(
        self,
        guild: discord.Guild,
        raw: dict,
        role_id_map: dict[int, discord.Role],
    ) -> dict:
        result = {}
        for target_id_str, data in raw.items():
            target_id = int(target_id_str)
            allow = discord.Permissions(data["allow"])
            deny = discord.Permissions(data["deny"])
            overwrite = discord.PermissionOverwrite.from_pair(allow, deny)
            if data["type"] == "role":
                role = role_id_map.get(target_id) or guild.get_role(target_id)
                if role:
                    result[role] = overwrite
            else:
                member = guild.get_member(target_id)
                if member:
                    result[member] = overwrite
        return result

    def _restore_bot_config(self, guild_id: int, cfg: dict):
        try:
            if "welcome" in cfg:
                w = cfg["welcome"]
                self.db.execute(
                    "INSERT OR REPLACE INTO welcome_config (guild_id, channel_id, message_text) VALUES (?, ?, ?)",
                    (guild_id, w.get("channel_id"), w.get("message_text")),
                )
        except Exception as e:
            self.logger.warning(f"[restore:{guild_id}] Failed to restore welcome config: {e}")

        try:
            for role_id in cfg.get("auto_roles", []):
                self.db.execute(
                    "INSERT OR IGNORE INTO auto_roles (guild_id, role_id) VALUES (?, ?)",
                    (guild_id, role_id),
                )
        except Exception as e:
            self.logger.warning(f"[restore:{guild_id}] Failed to restore auto_roles: {e}")

        try:
            for lr in cfg.get("level_roles", []):
                self.db.execute(
                    "INSERT OR REPLACE INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?)",
                    (guild_id, lr["level"], lr["role_id"]),
                )
        except Exception as e:
            self.logger.warning(f"[restore:{guild_id}] Failed to restore level_roles: {e}")

        try:
            if "automod" in cfg:
                a = cfg["automod"]
                self.db.execute(
                    "INSERT OR REPLACE INTO automod_settings "
                    "(guild_id, bad_words, anti_invite, anti_links, anti_caps, max_mentions, max_emojis, exempt_roles) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (guild_id, a.get("bad_words"), a.get("anti_invite"), a.get("anti_links"),
                     a.get("anti_caps"), a.get("max_mentions"), a.get("max_emojis"), a.get("exempt_roles")),
                )
        except Exception as e:
            self.logger.warning(f"[restore:{guild_id}] Failed to restore automod settings: {e}")

        try:
            if "automod_actions" in cfg:
                aa = cfg["automod_actions"]
                self.db.execute(
                    "INSERT OR REPLACE INTO automod_actions (guild_id, warn_threshold, action, duration_minutes) VALUES (?, ?, ?, ?)",
                    (guild_id, aa["warn_threshold"], aa["action"], aa["duration_minutes"]),
                )
        except Exception as e:
            self.logger.warning(f"[restore:{guild_id}] Failed to restore automod_actions: {e}")

        try:
            if "mod_logs_channel_id" in cfg:
                self.db.execute(
                    "INSERT OR REPLACE INTO mod_logs (guild_id, channel_id) VALUES (?, ?)",
                    (guild_id, cfg["mod_logs_channel_id"]),
                )
        except Exception as e:
            self.logger.warning(f"[restore:{guild_id}] Failed to restore mod_logs: {e}")

        try:
            for s in cfg.get("stats_channels", []):
                self.db.execute(
                    "INSERT OR REPLACE INTO stats_channels (guild_id, stat_type, channel_id) VALUES (?, ?, ?)",
                    (guild_id, s["stat_type"], s["channel_id"]),
                )
        except Exception as e:
            self.logger.warning(f"[restore:{guild_id}] Failed to restore stats_channels: {e}")

        try:
            if "birthday_settings" in cfg:
                b = cfg["birthday_settings"]
                self.db.execute(
                    "INSERT OR REPLACE INTO birthday_settings (guild_id, channel_id, role_id) VALUES (?, ?, ?)",
                    (guild_id, b.get("channel_id"), b.get("role_id")),
                )
        except Exception as e:
            self.logger.warning(f"[restore:{guild_id}] Failed to restore birthday_settings: {e}")

        try:
            for b in cfg.get("birthdays", []):
                self.db.execute(
                    "INSERT OR REPLACE INTO birthdays (user_id, guild_id, month, day) VALUES (?, ?, ?, ?)",
                    (b["user_id"], guild_id, b["month"], b["day"]),
                )
        except Exception as e:
            self.logger.warning(f"[restore:{guild_id}] Failed to restore birthdays: {e}")

        try:
            if "voice_hub_id" in cfg:
                self.db.execute(
                    "INSERT OR REPLACE INTO voice_hubs (guild_id, hub_id) VALUES (?, ?)",
                    (guild_id, cfg["voice_hub_id"]),
                )
        except Exception as e:
            self.logger.warning(f"[restore:{guild_id}] Failed to restore voice_hubs: {e}")

        try:
            for t in cfg.get("ticket_templates", []):
                self.db.execute(
                    "INSERT OR IGNORE INTO ticket_templates (guild_id, name, content) VALUES (?, ?, ?)",
                    (guild_id, t["name"], t["content"]),
                )
        except Exception as e:
            self.logger.warning(f"[restore:{guild_id}] Failed to restore ticket_templates: {e}")

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    @app_commands.command(name="backup_create", description="Create a full server backup and DM it to you. (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_create(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            backup = await self._create_backup(interaction.guild)
            self._save_locally(interaction.guild.id, backup)
            file, _ = self._to_file(backup, interaction.guild.name)
            embed = self._build_summary_embed(backup, "🗄️ Server Backup", discord.Color.blurple())
            try:
                await interaction.user.send(embed=embed, file=file)
                await interaction.followup.send("✅ Backup complete! Check your DMs.", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ Couldn't DM you. Please enable DMs from server members and try again.",
                    ephemeral=True,
                )
        except Exception as e:
            await interaction.followup.send(f"❌ Backup failed: {e}", ephemeral=True)

    @app_commands.command(name="backup_restore", description="Restore a server from a backup JSON file. (Admin only)")
    @app_commands.describe(
        backup_file="The backup .json file to restore from",
        confirm="Set to True to execute the restore. Leave False to preview what will be created.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_restore(
        self,
        interaction: discord.Interaction,
        backup_file: discord.Attachment,
        confirm: bool = False,
    ):
        await interaction.response.defer(ephemeral=True)

        if not backup_file.filename.endswith(".json"):
            await interaction.followup.send("❌ Please attach a `.json` backup file.", ephemeral=True)
            return

        try:
            raw = await backup_file.read()
            backup = json.loads(raw.decode("utf-8"))
        except Exception:
            await interaction.followup.send("❌ Could not parse the file. Make sure it's a valid JSON.", ephemeral=True)
            return

        if not {"meta", "roles", "categories", "channels", "bot_config"}.issubset(backup.keys()):
            await interaction.followup.send("❌ This doesn't look like a valid DenyCord backup file.", ephemeral=True)
            return

        roles_count = len(backup.get("roles", []))
        cats_count = len(backup.get("categories", []))
        channels_count = len(backup.get("channels", []))
        levels_count = len(backup.get("member_levels", []))
        warnings_count = len(backup.get("warnings", []))
        original = backup["meta"].get("guild_name", "Unknown")
        created = backup["meta"].get("created_at", "")[:10]

        if not confirm:
            embed = discord.Embed(
                title="🗄️ Restore Preview",
                description=(
                    f"Backup from **{original}** on `{created}`.\n\n"
                    "**What will be created:**\n"
                    f"• `{roles_count}` roles\n"
                    f"• `{cats_count}` categories\n"
                    f"• `{channels_count}` channels\n"
                    f"• `{levels_count}` XP records\n"
                    f"• `{warnings_count}` warning records\n"
                    "• Bot config (welcome, automod, tickets, stats, birthdays, etc.)\n\n"
                    "**What will NOT change:**\n"
                    "• Existing roles/channels are kept — new ones are added alongside them\n"
                    "• Server name, icon, and Discord-level settings\n"
                    "• Emojis (URLs saved in backup for reference only)\n\n"
                    "⚠️ Run again with `confirm: True` to execute."
                ),
                color=discord.Color.orange(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # === Execute restore ===
        guild = interaction.guild
        errors = []
        results = {"roles": 0, "categories": 0, "channels": 0, "levels": 0, "warnings": 0}

        # 1. Roles — build old_id -> new_role map for overwrite resolution
        role_id_map: dict[int, discord.Role] = {}
        for role_data in sorted(backup.get("roles", []), key=lambda r: r["position"]):
            try:
                new_role = await guild.create_role(
                    name=role_data["name"],
                    color=discord.Color(role_data["color"]),
                    hoist=role_data["hoist"],
                    mentionable=role_data["mentionable"],
                    permissions=discord.Permissions(role_data["permissions"]),
                    reason="Restored from backup",
                )
                role_id_map[role_data["id"]] = new_role
                results["roles"] += 1
            except Exception as e:
                errors.append(f"Role '{role_data['name']}': {e}")

        # 2. Categories — build old_id -> new_category map for channel placement
        cat_id_map: dict[int, discord.CategoryChannel] = {}
        for cat_data in sorted(backup.get("categories", []), key=lambda c: c["position"]):
            overwrites = self._deserialize_overwrites(guild, cat_data.get("overwrites", {}), role_id_map)
            try:
                new_cat = await guild.create_category(
                    name=cat_data["name"],
                    overwrites=overwrites,
                    reason="Restored from backup",
                )
                cat_id_map[cat_data["id"]] = new_cat
                results["categories"] += 1
            except Exception as e:
                errors.append(f"Category '{cat_data['name']}': {e}")

        # 3. Channels
        for ch_data in sorted(backup.get("channels", []), key=lambda c: c["position"]):
            overwrites = self._deserialize_overwrites(guild, ch_data.get("overwrites", {}), role_id_map)
            category = cat_id_map.get(ch_data.get("category_id"))
            ch_type = ch_data.get("type", "text")
            try:
                if "voice" in ch_type:
                    await guild.create_voice_channel(
                        name=ch_data["name"], category=category, overwrites=overwrites,
                        bitrate=ch_data.get("bitrate", 64000),
                        user_limit=ch_data.get("user_limit", 0),
                        reason="Restored from backup",
                    )
                elif "stage" in ch_type:
                    await guild.create_stage_channel(
                        name=ch_data["name"], category=category, overwrites=overwrites,
                        reason="Restored from backup",
                    )
                elif "forum" in ch_type:
                    await guild.create_forum(
                        name=ch_data["name"], category=category, overwrites=overwrites,
                        reason="Restored from backup",
                    )
                else:
                    await guild.create_text_channel(
                        name=ch_data["name"], category=category, overwrites=overwrites,
                        topic=ch_data.get("topic"),
                        slowmode_delay=ch_data.get("slowmode", 0),
                        nsfw=ch_data.get("nsfw", False),
                        reason="Restored from backup",
                    )
                results["channels"] += 1
            except Exception as e:
                errors.append(f"Channel '{ch_data['name']}': {e}")

        # 4. Bot config
        self._restore_bot_config(guild.id, backup.get("bot_config", {}))

        # 5. Member levels
        for ld in backup.get("member_levels", []):
            try:
                self.db.execute(
                    "INSERT OR REPLACE INTO levels (user_id, guild_id, xp, level) VALUES (?, ?, ?, ?)",
                    (ld["user_id"], guild.id, ld["xp"], ld["level"]),
                )
                results["levels"] += 1
            except Exception:
                pass

        # 6. Warnings
        for wd in backup.get("warnings", []):
            try:
                self.db.execute(
                    "INSERT INTO warnings (user_id, guild_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (wd["user_id"], guild.id, wd["moderator_id"], wd["reason"], wd["timestamp"]),
                )
                results["warnings"] += 1
            except Exception:
                pass

        embed = discord.Embed(
            title="✅ Restore Complete",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Roles created", value=results["roles"], inline=True)
        embed.add_field(name="Categories created", value=results["categories"], inline=True)
        embed.add_field(name="Channels created", value=results["channels"], inline=True)
        embed.add_field(name="XP records", value=results["levels"], inline=True)
        embed.add_field(name="Warnings", value=results["warnings"], inline=True)
        if errors:
            error_preview = "\n".join(errors[:8])
            if len(errors) > 8:
                error_preview += f"\n... and {len(errors) - 8} more"
            embed.add_field(name=f"⚠️ {len(errors)} issue(s)", value=f"```{error_preview}```", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="backup_schedule", description="Set up automatic scheduled backups to a channel. (Admin only)")
    @app_commands.describe(
        channel="Channel to post backup files in",
        hours="How often to back up, in hours (e.g. 24 = daily)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_schedule(self, interaction: discord.Interaction, channel: discord.TextChannel, hours: int):
        if not (1 <= hours <= 8760):
            await interaction.response.send_message("❌ Hours must be between 1 and 8760 (1 year).", ephemeral=True)
            return

        existing = self.db.fetchone("SELECT guild_id FROM backup_settings WHERE guild_id = ?", (interaction.guild.id,))
        if existing:
            self.db.execute(
                "UPDATE backup_settings SET channel_id = ?, interval_hours = ? WHERE guild_id = ?",
                (channel.id, hours, interaction.guild.id),
            )
        else:
            self.db.execute(
                "INSERT INTO backup_settings (guild_id, channel_id, interval_hours) VALUES (?, ?, ?)",
                (interaction.guild.id, channel.id, hours),
            )

        label = f"{hours} hour{'s' if hours != 1 else ''}"
        embed = discord.Embed(
            title="🗄️ Backup Schedule Set",
            description=f"Automatic backups every **{label}** → {channel.mention}",
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="backup_unschedule", description="Disable automatic scheduled backups. (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_unschedule(self, interaction: discord.Interaction):
        existing = self.db.fetchone(
            "SELECT interval_hours FROM backup_settings WHERE guild_id = ?", (interaction.guild.id,)
        )
        if not existing or not existing[0]:
            await interaction.response.send_message("❌ No backup schedule is currently active.", ephemeral=True)
            return

        self.db.execute(
            "UPDATE backup_settings SET channel_id = NULL, interval_hours = NULL WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        await interaction.response.send_message("🗑️ Scheduled backups disabled.", ephemeral=True)

    # -------------------------------------------------------------------------
    # Error handlers
    # -------------------------------------------------------------------------

    @backup_create.error
    @backup_restore.error
    @backup_schedule.error
    @backup_unschedule.error
    async def backup_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You need Administrator permission.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Backup(bot))
