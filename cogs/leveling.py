import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import random
import time
import math

class LevelRewardView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.selected_level = None
        self.selected_role = None

    @discord.ui.select(placeholder="Select Level...", options=[
        discord.SelectOption(label="Level 1", value="1"),
        discord.SelectOption(label="Level 5", value="5"),
        discord.SelectOption(label="Level 10", value="10"),
        discord.SelectOption(label="Level 15", value="15"),
        discord.SelectOption(label="Level 20", value="20"),
        discord.SelectOption(label="Level 25", value="25"),
        discord.SelectOption(label="Level 30", value="30"),
        discord.SelectOption(label="Level 40", value="40"),
        discord.SelectOption(label="Level 50", value="50"),
        discord.SelectOption(label="Level 100", value="100"),
    ])
    async def select_level(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_level = int(select.values[0])
        await interaction.response.defer()

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Select Role...")
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        self.selected_role = select.values[0]
        await interaction.response.defer()
    
    @discord.ui.button(label="Save Configuration", style=discord.ButtonStyle.green)
    async def save(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True) # Acknowledge the interaction
        
        if not self.selected_level or not self.selected_role:
             return await interaction.followup.send("Please select both a level and a role.", ephemeral=True)
        
        # Save to DB
        conn = sqlite3.connect(self.cog.db_name)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?)", 
                  (interaction.guild.id, self.selected_level, self.selected_role.id))
        conn.commit()
        conn.close()
        
        await interaction.followup.send(f"✅ Set **{self.selected_role.name}** for **Level {self.selected_level}**.", ephemeral=True)

    @discord.ui.button(label="View Config", style=discord.ButtonStyle.grey)
    async def view_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(self.cog.db_name)
        c = conn.cursor()
        c.execute("SELECT level, role_id FROM level_roles WHERE guild_id = ? ORDER BY level", (interaction.guild.id,))
        results = c.fetchall()
        conn.close()
        
        if not results:
             return await interaction.response.send_message("No level rewards configured.", ephemeral=True)
        
        desc = ""
        for level, role_id in results:
            role = interaction.guild.get_role(role_id)
            role_name = role.mention if role else f"Deleted Role ({role_id})"
            desc += f"**Level {level}:** {role_name}\n"
            
        embed = discord.Embed(title="Level Rewards Config", description=desc, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)


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
        c.execute('''CREATE TABLE IF NOT EXISTS level_roles
                     (guild_id INTEGER, level INTEGER, role_id INTEGER,
                      PRIMARY KEY (guild_id, level))''')
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
                
                # Check for role reward
                c.execute("SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?", (guild_id, new_level))
                role_result = c.fetchone()
                if role_result:
                    role_id = role_result[0]
                    role = message.guild.get_role(role_id)
                    if role:
                        try:
                            await message.author.add_roles(role)
                            await message.channel.send(f"🏆 You have been awarded the **{role.name}** role!")
                        except discord.Forbidden:
                            pass # Bot missing permissions

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

    @app_commands.command(name="setup_rewards", description="Configure level-up role rewards")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_rewards(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Setup Level Rewards", description="Use the menu below to assign roles to specific levels.", color=discord.Color.blue())
        view = LevelRewardView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Leveling(bot))
