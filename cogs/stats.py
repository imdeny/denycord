import discord
from discord.ext import commands, tasks
from discord import app_commands

STAT_TYPES = {
    "members": ("Members: {}", lambda g: g.member_count or 0),
    "humans":  ("Humans: {}",  lambda g: sum(1 for m in g.members if not m.bot)),
    "bots":    ("Bots: {}",    lambda g: sum(1 for m in g.members if m.bot)),
    "boosts":  ("Boosts: {}",  lambda g: g.premium_subscription_count or 0),
}

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_stats.start()

    def cog_unload(self):
        self.update_stats.cancel()

    async def update_guild_stats(self, guild):
        rows = self.bot.db.fetchall(
            "SELECT stat_type, channel_id FROM stats_channels WHERE guild_id = ?",
            (guild.id,)
        )
        for stat_type, channel_id in rows:
            if stat_type not in STAT_TYPES:
                continue
            channel = guild.get_channel(channel_id)
            if not channel:
                continue
            fmt, value_fn = STAT_TYPES[stat_type]
            new_name = fmt.format(value_fn(guild))
            if channel.name != new_name:
                try:
                    await channel.edit(name=new_name, reason="Stats update")
                except (discord.Forbidden, discord.HTTPException):
                    pass

    @tasks.loop(minutes=10)
    async def update_stats(self):
        for guild in self.bot.guilds:
            await self.update_guild_stats(guild)

    @update_stats.before_loop
    async def before_update_stats(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.update_guild_stats(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.update_guild_stats(member.guild)

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        if before.premium_subscription_count != after.premium_subscription_count:
            await self.update_guild_stats(after)

    @app_commands.command(name="stats_setup", description="Create a voice channel that displays a live server statistic")
    @app_commands.describe(stat_type="Which statistic to display")
    @app_commands.choices(stat_type=[
        app_commands.Choice(name="Total Members", value="members"),
        app_commands.Choice(name="Human Members", value="humans"),
        app_commands.Choice(name="Bots",          value="bots"),
        app_commands.Choice(name="Server Boosts", value="boosts"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def stats_setup(self, interaction: discord.Interaction, stat_type: str):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        existing = self.bot.db.fetchone(
            "SELECT channel_id FROM stats_channels WHERE guild_id = ? AND stat_type = ?",
            (guild.id, stat_type)
        )
        if existing:
            channel = guild.get_channel(existing[0])
            if channel:
                return await interaction.followup.send(
                    f"A **{stat_type}** stats channel already exists: {channel.mention}", ephemeral=True
                )

        fmt, value_fn = STAT_TYPES[stat_type]
        channel_name = fmt.format(value_fn(guild))

        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True),
                guild.me: discord.PermissionOverwrite(connect=True, manage_channels=True),
            }
            channel = await guild.create_voice_channel(
                name=channel_name, overwrites=overwrites, reason="Stats channel setup"
            )
            self.bot.db.execute(
                "INSERT OR REPLACE INTO stats_channels (guild_id, stat_type, channel_id) VALUES (?, ?, ?)",
                (guild.id, stat_type, channel.id)
            )
            await interaction.followup.send(f"Created stats channel: {channel.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to create channels.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="stats_remove", description="Remove a stats channel")
    @app_commands.describe(stat_type="Which stats channel to remove")
    @app_commands.choices(stat_type=[
        app_commands.Choice(name="Total Members", value="members"),
        app_commands.Choice(name="Human Members", value="humans"),
        app_commands.Choice(name="Bots",          value="bots"),
        app_commands.Choice(name="Server Boosts", value="boosts"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def stats_remove(self, interaction: discord.Interaction, stat_type: str):
        existing = self.bot.db.fetchone(
            "SELECT channel_id FROM stats_channels WHERE guild_id = ? AND stat_type = ?",
            (interaction.guild.id, stat_type)
        )
        if not existing:
            return await interaction.response.send_message("No stats channel found for that type.", ephemeral=True)

        channel = interaction.guild.get_channel(existing[0])
        if channel:
            try:
                await channel.delete(reason="Stats channel removed")
            except discord.Forbidden:
                pass

        self.bot.db.execute(
            "DELETE FROM stats_channels WHERE guild_id = ? AND stat_type = ?",
            (interaction.guild.id, stat_type)
        )
        await interaction.response.send_message(f"Removed **{stat_type}** stats channel.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Stats(bot))
