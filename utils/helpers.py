import re
import discord
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Duration parsing
# ---------------------------------------------------------------------------

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
    """Format a number of seconds into a human-readable string like '2 hours, 30 minutes'."""
    seconds = int(seconds)
    parts = []
    for unit, label in [
        (86400 * 365, "year"),
        (86400 * 7, "week"),
        (86400, "day"),
        (3600, "hour"),
        (60, "minute"),
        (1, "second"),
    ]:
        if seconds >= unit:
            val = seconds // unit
            parts.append(f"{val} {label}{'s' if val != 1 else ''}")
            seconds %= unit
    return ", ".join(parts) if parts else "0 seconds"


# ---------------------------------------------------------------------------
# Moderation embeds
# ---------------------------------------------------------------------------

def make_mod_embed(title: str, color: discord.Color, user: discord.abc.User) -> discord.Embed:
    """Create a standard moderation log embed pre-populated with author info."""
    embed = discord.Embed(title=title, color=color, timestamp=datetime.now(timezone.utc))
    embed.set_author(name=user.name, icon_url=user.display_avatar.url)
    return embed
