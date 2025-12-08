import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import datetime
import random
import asyncio

def parse_duration(duration_str):
    """Parses a duration string like '10s', '1h', '2d' into seconds."""
    units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    unit = duration_str[-1].lower()
    try:
        val = int(duration_str[:-1])
        return val * units.get(unit, 1) # Default to seconds if no unit? Or error?
    except:
        return None

class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_name = "bot_database.db"
        self.init_db()
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        # status: active, ended
        c.execute('''CREATE TABLE IF NOT EXISTS giveaways
                     (message_id INTEGER PRIMARY KEY, channel_id INTEGER, 
                      prize TEXT, end_time TIMESTAMP, winners_count INTEGER, status TEXT)''')
        conn.commit()
        conn.close()

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

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("INSERT INTO giveaways (message_id, channel_id, prize, end_time, winners_count, status) VALUES (?, ?, ?, ?, ?, ?)",
                  (message.id, interaction.channel.id, prize, end_time, winners, "active"))
        conn.commit()
        conn.close()

    @app_commands.command(name="gend", description="End a giveaway immediately")
    @app_commands.describe(message_id="The message ID of the giveaway")
    @app_commands.checks.has_permissions(manage_events=True)
    async def gend(self, interaction: discord.Interaction, message_id: str):
        try:
             video_id = int(message_id) # variable name typo in thought process, fixed here
             msg_id_int = int(message_id)
        except ValueError:
             return await interaction.response.send_message("Invalid ID", ephemeral=True)

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT channel_id, prize, winners_count FROM giveaways WHERE message_id = ? AND status = 'active'", (msg_id_int,))
        result = c.fetchone()
        
        if not result:
            conn.close()
            return await interaction.response.send_message("Giveaway not found or already ended.", ephemeral=True)
            
        # Update DB first to prevent race conditions (though simple bot)
        c.execute("UPDATE giveaways SET status = 'ended' WHERE message_id = ?", (msg_id_int,))
        conn.commit()
        conn.close()
        
        # Trigger end logic
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

        # Logic: Just fetch the message and pick a random reactor who isn't a bot
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
        await interaction.response.send_message(f"🎉 The new winner is {winner.mention}! Congratulations!", ephemeral=False) # Public reroll


    async def end_giveaway(self, message_id, channel_id, prize, winners_count):
        channel = self.bot.get_channel(channel_id)
        # If channel not in cache, try fetch? Or just fail gracefully.
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
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        now = datetime.datetime.now()
        c.execute("SELECT message_id, channel_id, prize, winners_count FROM giveaways WHERE status = 'active' AND end_time <= ?", (now,))
        ended = c.fetchall()
        
        for row in ended:
            message_id, channel_id, prize, winners_count = row
            c.execute("UPDATE giveaways SET status = 'ended' WHERE message_id = ?", (message_id,))
            conn.commit()
            
            # Using asyncio.create_task to not block the loop
            asyncio.create_task(self.end_giveaway(message_id, channel_id, prize, winners_count))
            
        conn.close()

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Giveaways(bot))
