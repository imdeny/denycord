import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import random
import asyncio

def parse_duration(duration_str):
    """Parses a duration string like '10s', '1h', '2d' into seconds."""
    units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    unit = duration_str[-1].lower()
    try:
        val = int(duration_str[:-1])
        return val * units.get(unit, 1)
    except:
        return None

class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @app_commands.command(name="gstart", description="Start a giveaway")
    @app_commands.describe(duration="Duration (e.g. 10m, 1h, 2d)", winners="Number of winners", prize="Prize to win")
    @app_commands.checks.has_permissions(manage_events=True)
    async def gstart(self, interaction: discord.Interaction, duration: str, winners: int, prize: str):
        seconds = parse_duration(duration)
        if not seconds:
            return await interaction.response.send_message("Invalid duration format. Use 10s, 10m, 1h, or 1d.", ephemeral=True)

        end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        end_timestamp = int(end_time.timestamp())

        embed = discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{end_timestamp}:R>", color=discord.Color.purple())
        embed.set_footer(text="React with 🎉 to enter!")

        await interaction.response.send_message("Giveaway started!", ephemeral=True)
        message = await interaction.channel.send(embed=embed)
        await message.add_reaction("🎉")

        self.bot.db.execute("INSERT INTO giveaways (message_id, channel_id, prize, end_time, winners_count, status) VALUES (?, ?, ?, ?, ?, ?)",
                  (message.id, interaction.channel.id, prize, end_time, winners, "active"))

    @app_commands.command(name="gend", description="End a giveaway immediately")
    @app_commands.describe(message_id="The message ID of the giveaway")
    @app_commands.checks.has_permissions(manage_events=True)
    async def gend(self, interaction: discord.Interaction, message_id: str):
        try:
             msg_id_int = int(message_id)
        except ValueError:
             return await interaction.response.send_message("Invalid ID", ephemeral=True)

        result = self.bot.db.fetchone("SELECT channel_id, prize, winners_count FROM giveaways WHERE message_id = ? AND status = 'active'", (msg_id_int,))
        
        if not result:
            return await interaction.response.send_message("Giveaway not found or already ended.", ephemeral=True)
            
        self.bot.db.execute("UPDATE giveaways SET status = 'ended' WHERE message_id = ?", (msg_id_int,))
        
        channel_id, prize, winners_count = result
        await self.end_giveaway(msg_id_int, channel_id, prize, winners_count)
        
        await interaction.response.send_message("Giveaway ended.", ephemeral=True)

    @app_commands.command(name="greroll", description="Reroll a giveaway winner")
    @app_commands.describe(message_id="The message ID of the giveaway")
    @app_commands.checks.has_permissions(manage_events=True)
    async def greroll(self, interaction: discord.Interaction, message_id: str):
        try:
             msg_id_int = int(message_id)
        except ValueError:
             return await interaction.response.send_message("Invalid ID", ephemeral=True)

        try:
            message = await interaction.channel.fetch_message(msg_id_int)
        except discord.NotFound:
            return await interaction.response.send_message("Giveaway message not found.", ephemeral=True)
            
        reaction = discord.utils.get(message.reactions, emoji="🎉")
        if not reaction:
            return await interaction.response.send_message("No 🎉 reaction found on that message.", ephemeral=True)
            
        users = []
        async for user in reaction.users():
            if not user.bot:
                users.append(user)
                
        if not users:
            return await interaction.response.send_message("No valid entrants to reroll.", ephemeral=True)
            
        winner = random.choice(users)
        await interaction.response.send_message(f"🎉 The new winner is {winner.mention}! Congratulations!", ephemeral=False)

    async def end_giveaway(self, message_id, channel_id, prize, winners_count):
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
            
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            return
            
        embed = message.embeds[0]
        embed.description = f"**Prize:** {prize}\n**Winners:** {winners_count}\n**Ended**"
        embed.color = discord.Color.greyple()
        await message.edit(embed=embed)
        
        reaction = discord.utils.get(message.reactions, emoji="🎉")
        if not reaction:
            await channel.send(f"Giveaway for **{prize}** ended, but no one entered! 😞")
            return
            
        users = []
        async for user in reaction.users():
            if not user.bot:
                users.append(user)
                
        if not users:
            await channel.send(f"Giveaway for **{prize}** ended, but no one entered! 😞")
            return
            
        if len(users) < winners_count:
            winners = users
        else:
            winners = random.sample(users, winners_count)
            
        winner_mentions = ", ".join([w.mention for w in winners])
        await channel.send(f"🎉 Congratulations {winner_mentions}! You won **{prize}**! 🎉")

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        now = datetime.datetime.now()
        ended = self.bot.db.fetchall("SELECT message_id, channel_id, prize, winners_count FROM giveaways WHERE status = 'active' AND end_time <= ?", (now,))
        
        for row in ended:
            message_id, channel_id, prize, winners_count = row
            self.bot.db.execute("UPDATE giveaways SET status = 'ended' WHERE message_id = ?", (message_id,))
            
            asyncio.create_task(self.end_giveaway(message_id, channel_id, prize, winners_count))

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Giveaways(bot))
