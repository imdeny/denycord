import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone, timedelta
import re


MAX_REMINDERS_PER_USER = 5
MAX_DURATION_SECONDS = 365 * 24 * 3600  # 1 year

DURATION_REGEX = re.compile(
    r"(?:(\d+)\s*y(?:ears?)?)?"
    r"\s*(?:(\d+)\s*w(?:eeks?)?)?"
    r"\s*(?:(\d+)\s*d(?:ays?)?)?"
    r"\s*(?:(\d+)\s*h(?:ours?)?)?"
    r"\s*(?:(\d+)\s*m(?:in(?:utes?)?)?)?"
    r"\s*(?:(\d+)\s*s(?:ec(?:onds?)?)?)?",
    re.IGNORECASE,
)


def parse_duration(text: str) -> int | None:
    """Parse a duration string like '2h30m' into total seconds. Returns None if invalid."""
    text = text.strip()
    match = DURATION_REGEX.fullmatch(text)
    if not match or not any(match.groups()):
        return None
    years, weeks, days, hours, minutes, seconds = (int(v) if v else 0 for v in match.groups())
    total = (
        years * 365 * 24 * 3600
        + weeks * 7 * 24 * 3600
        + days * 24 * 3600
        + hours * 3600
        + minutes * 60
        + seconds
    )
    return total if total > 0 else None


def format_duration(seconds: int) -> str:
    parts = []
    for unit, label in [(86400 * 365, "year"), (86400 * 7, "week"), (86400, "day"), (3600, "hour"), (60, "minute"), (1, "second")]:
        if seconds >= unit:
            val = seconds // unit
            parts.append(f"{val} {label}{'s' if val != 1 else ''}")
            seconds %= unit
    return ", ".join(parts) if parts else "0 seconds"


def format_timestamp(ts: float) -> str:
    return f"<t:{int(ts)}:R>"


class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    # -------------------------------------------------------------------------
    # Background task
    # -------------------------------------------------------------------------

    @tasks.loop(seconds=30)
    async def reminder_loop(self):
        now = datetime.now(timezone.utc).timestamp()
        due = self.db.fetchall(
            "SELECT id, user_id, guild_id, channel_id, message, deliver_dm FROM reminders WHERE fire_at <= ?",
            (now,),
        )

        for row_id, user_id, guild_id, channel_id, message, deliver_dm in due:
            self.db.execute("DELETE FROM reminders WHERE id = ?", (row_id,))

            user = self.bot.get_user(user_id)
            if user is None:
                try:
                    user = await self.bot.fetch_user(user_id)
                except discord.NotFound:
                    continue

            embed = discord.Embed(
                title="⏰ Reminder!",
                description=message,
                color=discord.Color.yellow(),
            )
            embed.set_footer(text=f"Reminder #{row_id}")

            if deliver_dm:
                try:
                    await user.send(embed=embed)
                except discord.Forbidden:
                    pass
            else:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    try:
                        await channel.send(content=user.mention, embed=embed)
                    except discord.Forbidden:
                        pass

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    @app_commands.command(name="remind", description="Set a reminder. (e.g. duration: 2h30m  message: Call mom)")
    @app_commands.describe(
        duration="How long until the reminder fires (e.g. 30m, 2h, 1d, 1h30m)",
        message="What to remind you about",
        delivery="Where to deliver the reminder",
    )
    @app_commands.choices(delivery=[
        app_commands.Choice(name="DM me", value="dm"),
        app_commands.Choice(name="Here (this channel)", value="channel"),
    ])
    async def remind(
        self,
        interaction: discord.Interaction,
        duration: str,
        message: str,
        delivery: app_commands.Choice[str],
    ):
        # Validate duration
        total_seconds = parse_duration(duration)
        if total_seconds is None:
            await interaction.response.send_message(
                "❌ Invalid duration. Examples: `30m`, `2h`, `1d`, `1h30m`, `2d12h`.",
                ephemeral=True,
            )
            return

        if total_seconds > MAX_DURATION_SECONDS:
            await interaction.response.send_message(
                "❌ Maximum reminder duration is **1 year**.",
                ephemeral=True,
            )
            return

        # Check cap
        count = self.db.fetchone(
            "SELECT COUNT(*) FROM reminders WHERE user_id = ? AND guild_id = ?",
            (interaction.user.id, interaction.guild.id),
        )[0]
        if count >= MAX_REMINDERS_PER_USER:
            await interaction.response.send_message(
                f"❌ You already have **{MAX_REMINDERS_PER_USER}** pending reminders. Cancel one with `/reminders_cancel` first.",
                ephemeral=True,
            )
            return

        # Validate message length
        if len(message) > 500:
            await interaction.response.send_message(
                "❌ Reminder message must be 500 characters or fewer.",
                ephemeral=True,
            )
            return

        now = datetime.now(timezone.utc).timestamp()
        fire_at = now + total_seconds
        deliver_dm = 1 if delivery.value == "dm" else 0

        self.db.execute(
            "INSERT INTO reminders (user_id, guild_id, channel_id, message, fire_at, deliver_dm) VALUES (?, ?, ?, ?, ?, ?)",
            (interaction.user.id, interaction.guild.id, interaction.channel.id, message, fire_at, deliver_dm),
        )

        delivery_text = "via DM" if deliver_dm else f"in {interaction.channel.mention}"
        duration_text = format_duration(total_seconds)

        embed = discord.Embed(
            title="⏰ Reminder Set!",
            description=f"**{message}**",
            color=discord.Color.yellow(),
        )
        embed.add_field(name="Fires in", value=duration_text, inline=True)
        embed.add_field(name="Fires at", value=format_timestamp(fire_at), inline=True)
        embed.add_field(name="Delivery", value=delivery_text, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="reminders_list", description="View all your pending reminders.")
    async def reminders_list(self, interaction: discord.Interaction):
        rows = self.db.fetchall(
            "SELECT id, message, fire_at, deliver_dm FROM reminders WHERE user_id = ? AND guild_id = ? ORDER BY fire_at ASC",
            (interaction.user.id, interaction.guild.id),
        )

        if not rows:
            await interaction.response.send_message("You have no pending reminders.", ephemeral=True)
            return

        embed = discord.Embed(
            title="⏰ Your Pending Reminders",
            color=discord.Color.yellow(),
        )
        for row_id, message, fire_at, deliver_dm in rows:
            delivery = "DM" if deliver_dm else "Channel"
            short_msg = message if len(message) <= 60 else message[:57] + "..."
            embed.add_field(
                name=f"#{row_id} — {format_timestamp(fire_at)}",
                value=f"`{short_msg}`\nDelivery: {delivery}",
                inline=False,
            )
        embed.set_footer(text=f"{len(rows)}/{MAX_REMINDERS_PER_USER} reminders used")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="reminders_cancel", description="Cancel a pending reminder by its ID.")
    @app_commands.describe(reminder_id="The reminder ID (shown in /reminders_list)")
    async def reminders_cancel(self, interaction: discord.Interaction, reminder_id: int):
        row = self.db.fetchone(
            "SELECT id, message FROM reminders WHERE id = ? AND user_id = ? AND guild_id = ?",
            (reminder_id, interaction.user.id, interaction.guild.id),
        )
        if not row:
            await interaction.response.send_message(
                f"❌ No reminder with ID **#{reminder_id}** found. Use `/reminders_list` to see your reminders.",
                ephemeral=True,
            )
            return

        self.db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        short_msg = row[1] if len(row[1]) <= 60 else row[1][:57] + "..."
        await interaction.response.send_message(
            f"🗑️ Cancelled reminder **#{reminder_id}**: `{short_msg}`",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Reminders(bot))
