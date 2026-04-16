import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone
import calendar
import random


BIRTHDAY_PINK = discord.Color.from_str("#FF69B4")

BIRTHDAY_MESSAGES = [
    "🎉 Happy Birthday {mention}!! Hope your day is amazing!! 🎂",
    "🥳 It's {mention}'s birthday!! Go wish them a happy one!! 🎈",
    "🎂 {mention} is celebrating today — happy birthday!! 🎉",
    "🎈 Happy Birthday {mention}!! Make it a great one!! 🥳",
    "🎊 Shoutout to {mention} on their birthday today!! 🎂",
]


class Birthdays(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.announced_today: set[tuple[int, int]] = set()  # (guild_id, user_id)
        self.birthday_check_loop.start()

    def cog_unload(self):
        self.birthday_check_loop.cancel()

    # -------------------------------------------------------------------------
    # Background task — runs every minute, fires at UTC midnight
    # -------------------------------------------------------------------------

    @tasks.loop(minutes=1)
    async def birthday_check_loop(self):
        now = datetime.now(timezone.utc)

        # Reset the announced set at the start of each new UTC day
        if now.hour == 0 and now.minute == 0:
            self.announced_today.clear()

        # Only announce between 00:00 and 00:01 UTC
        if now.hour != 0 or now.minute != 0:
            return

        today_month = now.month
        today_day = now.day

        rows = self.db.fetchall(
            "SELECT user_id, guild_id FROM birthdays WHERE month = ? AND day = ?",
            (today_month, today_day),
        )

        for user_id, guild_id in rows:
            if (guild_id, user_id) in self.announced_today:
                continue

            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue

            settings = self.db.fetchone(
                "SELECT channel_id, role_id FROM birthday_settings WHERE guild_id = ?",
                (guild_id,),
            )
            if settings is None:
                continue

            channel_id, role_id = settings
            channel = guild.get_channel(channel_id)
            if channel is None:
                continue

            member = guild.get_member(user_id)
            if member is None:
                continue

            # Assign birthday role
            role = guild.get_role(role_id) if role_id else None
            if role:
                try:
                    await member.add_roles(role, reason="Birthday role")
                except discord.Forbidden:
                    pass

            message = random.choice(BIRTHDAY_MESSAGES).format(mention=member.mention)

            embed = discord.Embed(
                title="🎂 Happy Birthday!!",
                description=message,
                color=BIRTHDAY_PINK,
            )
            embed.set_thumbnail(url=member.display_avatar.url)

            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass

            self.announced_today.add((guild_id, user_id))

        await self._remove_expired_birthday_roles(today_month, today_day)

    @birthday_check_loop.before_loop
    async def before_birthday_check(self):
        await self.bot.wait_until_ready()

    async def _remove_expired_birthday_roles(self, current_month: int, current_day: int):
        """Remove birthday roles from anyone whose birthday is not today."""
        all_settings = self.db.fetchall(
            "SELECT guild_id, role_id FROM birthday_settings WHERE role_id IS NOT NULL"
        )
        for guild_id, role_id in all_settings:
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue
            role = guild.get_role(role_id)
            if role is None or not role.members:
                continue

            # Batch query: fetch all members in the role whose birthday IS today
            member_ids = [m.id for m in role.members]
            placeholders = ",".join("?" * len(member_ids))
            rows = self.db.fetchall(
                f"SELECT user_id FROM birthdays WHERE guild_id = ? AND month = ? AND day = ? AND user_id IN ({placeholders})",
                (guild_id, current_month, current_day, *member_ids),
            )
            today_birthday_ids = {row[0] for row in rows}

            for member in role.members:
                if member.id not in today_birthday_ids:
                    try:
                        await member.remove_roles(role, reason="Birthday over")
                    except discord.Forbidden:
                        pass

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _validate_date(self, month: int, day: int) -> bool:
        if month < 1 or month > 12:
            return False
        max_day = calendar.monthrange(2000, month)[1]  # 2000 = leap year, covers Feb 29
        return 1 <= day <= max_day

    async def _get_or_create_birthday_role(self, guild: discord.Guild) -> discord.Role | None:
        settings = self.db.fetchone(
            "SELECT role_id FROM birthday_settings WHERE guild_id = ?", (guild.id,)
        )
        existing_role_id = settings[0] if settings else None

        if existing_role_id:
            role = guild.get_role(existing_role_id)
            if role:
                return role

        try:
            role = await guild.create_role(
                name="🎂 Birthday",
                color=BIRTHDAY_PINK,
                hoist=True,
                mentionable=False,
                permissions=discord.Permissions.none(),
                reason="Birthday system role",
            )
        except discord.Forbidden:
            return None

        # Hoist as high as possible (just below bot's top role)
        bot_member = guild.get_member(self.bot.user.id)
        if bot_member:
            top_bot_role = bot_member.top_role
            target_position = max(top_bot_role.position - 1, 1)
            try:
                await role.edit(position=target_position)
            except (discord.Forbidden, discord.HTTPException):
                pass

        self.db.execute(
            "UPDATE birthday_settings SET role_id = ? WHERE guild_id = ?",
            (role.id, guild.id),
        )
        return role

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    @app_commands.command(name="birthday_setup", description="Set the channel for birthday announcements. (Admin only)")
    @app_commands.describe(channel="Channel to send birthday announcements in")
    @app_commands.checks.has_permissions(administrator=True)
    async def birthday_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)

        existing = self.db.fetchone(
            "SELECT guild_id FROM birthday_settings WHERE guild_id = ?", (interaction.guild.id,)
        )
        if existing:
            self.db.execute(
                "UPDATE birthday_settings SET channel_id = ? WHERE guild_id = ?",
                (channel.id, interaction.guild.id),
            )
        else:
            self.db.execute(
                "INSERT INTO birthday_settings (guild_id, channel_id) VALUES (?, ?)",
                (interaction.guild.id, channel.id),
            )

        role = await self._get_or_create_birthday_role(interaction.guild)
        role_text = f"Birthday role {role.mention} created and hoisted." if role else "⚠️ Could not create the birthday role — check my permissions."

        embed = discord.Embed(
            title="🎂 Birthday System Ready!",
            description=f"Announcements → {channel.mention}\n{role_text}\n\nUsers can set their birthday with `/birthday_set`.",
            color=BIRTHDAY_PINK,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="birthday_set", description="Set your birthday.")
    @app_commands.describe(month="Your birth month (1–12)", day="Your birth day (1–31)")
    async def birthday_set(self, interaction: discord.Interaction, month: int, day: int):
        if not self._validate_date(month, day):
            await interaction.response.send_message(
                "❌ Invalid date. Use a real month (1–12) and day.", ephemeral=True
            )
            return

        settings = self.db.fetchone(
            "SELECT channel_id FROM birthday_settings WHERE guild_id = ?", (interaction.guild.id,)
        )
        if not settings:
            await interaction.response.send_message(
                "❌ The birthday system hasn't been set up yet. Ask an admin to run `/birthday_setup`.",
                ephemeral=True,
            )
            return

        self.db.execute(
            "INSERT OR REPLACE INTO birthdays (user_id, guild_id, month, day) VALUES (?, ?, ?, ?)",
            (interaction.user.id, interaction.guild.id, month, day),
        )

        month_name = calendar.month_name[month]
        await interaction.response.send_message(
            f"🎂 Birthday set to **{month_name} {day}**. We'll celebrate you! 🥳",
            ephemeral=True,
        )

    @app_commands.command(name="birthday_remove", description="Remove your birthday from this server.")
    async def birthday_remove(self, interaction: discord.Interaction):
        existing = self.db.fetchone(
            "SELECT month FROM birthdays WHERE user_id = ? AND guild_id = ?",
            (interaction.user.id, interaction.guild.id),
        )
        if not existing:
            await interaction.response.send_message("❌ You don't have a birthday set here.", ephemeral=True)
            return

        self.db.execute(
            "DELETE FROM birthdays WHERE user_id = ? AND guild_id = ?",
            (interaction.user.id, interaction.guild.id),
        )
        await interaction.response.send_message("🗑️ Your birthday has been removed.", ephemeral=True)

    @app_commands.command(name="birthday_list", description="See all upcoming birthdays in this server.")
    async def birthday_list(self, interaction: discord.Interaction):
        await interaction.response.defer()

        rows = self.db.fetchall(
            "SELECT user_id, month, day FROM birthdays WHERE guild_id = ? ORDER BY month, day",
            (interaction.guild.id,),
        )

        if not rows:
            await interaction.followup.send("No birthdays have been set in this server yet.")
            return

        now = datetime.now(timezone.utc)

        def days_until(month, day):
            year = now.year
            try:
                bday = datetime(year, month, day, tzinfo=timezone.utc)
            except ValueError:
                bday = datetime(year, month, 28, tzinfo=timezone.utc)
            if bday.date() < now.date():
                try:
                    bday = datetime(year + 1, month, day, tzinfo=timezone.utc)
                except ValueError:
                    bday = datetime(year + 1, month, 28, tzinfo=timezone.utc)
            return (bday.date() - now.date()).days

        lines = []
        for user_id, month, day in rows:
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"Unknown ({user_id})"
            month_name = calendar.month_abbr[month]
            is_today = month == now.month and day == now.day
            until = days_until(month, day)
            suffix = " 🎂 **TODAY!**" if is_today else f" *(in {until}d)*"
            lines.append(f"**{name}** — {month_name} {day}{suffix}")

        embed = discord.Embed(
            title="🎂 Server Birthdays",
            description="\n".join(lines[:20]),
            color=BIRTHDAY_PINK,
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="birthday_check", description="Check a member's birthday.")
    @app_commands.describe(member="The member to look up")
    async def birthday_check(self, interaction: discord.Interaction, member: discord.Member):
        row = self.db.fetchone(
            "SELECT month, day FROM birthdays WHERE user_id = ? AND guild_id = ?",
            (member.id, interaction.guild.id),
        )
        if not row:
            await interaction.response.send_message(
                f"❌ **{member.display_name}** hasn't set their birthday here.", ephemeral=True
            )
            return

        month, day = row
        month_name = calendar.month_name[month]
        now = datetime.now(timezone.utc)
        is_today = month == now.month and day == now.day

        def days_until(m, d):
            year = now.year
            try:
                bday = datetime(year, m, d, tzinfo=timezone.utc)
            except ValueError:
                bday = datetime(year, m, 28, tzinfo=timezone.utc)
            if bday.date() < now.date():
                try:
                    bday = datetime(year + 1, m, d, tzinfo=timezone.utc)
                except ValueError:
                    bday = datetime(year + 1, m, 28, tzinfo=timezone.utc)
            return (bday.date() - now.date()).days

        until = days_until(month, day)
        timing = "🎂 **TODAY!!**" if is_today else f"in **{until} day{'s' if until != 1 else ''}**"

        embed = discord.Embed(
            title=f"🎂 {member.display_name}'s Birthday",
            description=f"**{month_name} {day}** — {timing}",
            color=BIRTHDAY_PINK,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @birthday_setup.error
    async def birthday_setup_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need Administrator permission to run this.", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Birthdays(bot))
