import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import random
import time
import math

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}
        self.db_name = "bot_database.db"
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS levels
                     (user_id INTEGER, guild_id INTEGER, xp INTEGER, level INTEGER,
                      PRIMARY KEY (user_id, guild_id))''')
        conn.commit()
        conn.close()

    def get_xp_for_level(self, level):
        return (level + 1) * 100

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        guild_id = message.guild.id
        
        # Cooldown check (60 seconds)
        key = (user_id, guild_id)
        if key in self.cooldowns and time.time() - self.cooldowns[key] < 60:
            return
        
        self.cooldowns[key] = time.time()

        # Add XP
        xp_gain = random.randint(15, 25)
        
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        c.execute("SELECT xp, level FROM levels WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        result = c.fetchone()
        
        if result:
            current_xp, current_level = result
            new_xp = current_xp + xp_gain
            
            xp_needed = self.get_xp_for_level(current_level)
            if new_xp >= xp_needed:
                new_level = current_level + 1
                new_xp -= xp_needed
                await message.channel.send(f"🎉 {message.author.mention} has leveled up to **Level {new_level}**!")
            else:
                new_level = current_level
                
            c.execute("UPDATE levels SET xp = ?, level = ? WHERE user_id = ? AND guild_id = ?", 
                      (new_xp, new_level, user_id, guild_id))
        else:
            c.execute("INSERT INTO levels (user_id, guild_id, xp, level) VALUES (?, ?, ?, ?)", 
                      (user_id, guild_id, xp_gain, 0))
            
        conn.commit()
        conn.close()

    @app_commands.command(name="rank", description="Check your current level and XP")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT xp, level FROM levels WHERE user_id = ? AND guild_id = ?", (member.id, interaction.guild.id))
        result = c.fetchone()
        conn.close()
        
        if result:
            xp, level = result
            xp_needed = self.get_xp_for_level(level)
            
            embed = discord.Embed(title=f"Rank - {member.name}", color=member.color)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="Level", value=str(level), inline=True)
            embed.add_field(name="XP", value=f"{xp}/{xp_needed}", inline=True)
            
            # Calculate progress bar
            progress = xp / xp_needed
            bar_length = 20
            filled_length = int(bar_length * progress)
            bar = "█" * filled_length + "░" * (bar_length - filled_length)
            embed.add_field(name="Progress", value=bar, inline=False)
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"{member.mention} has not earned any XP yet.", ephemeral=True)

    @app_commands.command(name="leaderboard", description="Shows the top 10 users in the server")
    async def leaderboard(self, interaction: discord.Interaction):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT user_id, level, xp FROM levels WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10", (interaction.guild.id,))
        results = c.fetchall()
        conn.close()
        
        if not results:
            await interaction.response.send_message("No data found for this server.", ephemeral=True)
            return
        
        embed = discord.Embed(title=f"Leaderboard - {interaction.guild.name}", color=discord.Color.gold())
        
        description = ""
        for i, (user_id, level, xp) in enumerate(results, 1):
            description += f"**{i}.** <@{user_id}> - Level {level} ({xp} XP)\n"
            
        embed.description = description
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Leveling(bot))
