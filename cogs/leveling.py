import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import random
import time
import math
import io
import functools
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

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
            
            await interaction.response.defer()
            try:
                img_bytes = await self.generate_rank_card(member, xp, level, xp_needed)
                file = discord.File(fp=io.BytesIO(img_bytes), filename="rank.png")
                await interaction.followup.send(file=file)
            except Exception as e:
                await interaction.followup.send(f"Error generating rank card: {e}")
                
        else:
            await interaction.response.send_message(f"{member.mention} has not earned any XP yet.", ephemeral=True)

    async def generate_rank_card(self, member, xp, level, xp_needed):
        # Download Avatar
        avatar_bytes = await member.display_avatar.with_format("png").read()
        
        # Run CPU-bound task in executor
        fn = functools.partial(self._process_rank_card, member.name, member.discriminator, avatar_bytes, xp, level, xp_needed)
        img_bytes = await self.bot.loop.run_in_executor(None, fn)
        return img_bytes

    def _process_rank_card(self, username, discriminator, avatar_bytes, xp, level, xp_needed):
        width = 900
        height = 250
        
        # Solid matte black/dark grey - extremely clean
        bg_color = (18, 18, 18) 
        image = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(image)
        
        # Avatar (Large, Left, No heavy borders, just clean)
        avatar_size = 180
        avatar_x = 40
        avatar_y = 35
        
        try:
            avatar_image = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar_image = avatar_image.resize((avatar_size, avatar_size), resample=Image.Resampling.LANCZOS)
            
            # Circular Mask
            mask = Image.new("L", (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
            
            # Apply mask
            output = ImageOps.fit(avatar_image, mask.size, centering=(0.5, 0.5))
            output.putalpha(mask)
            
            image.paste(output, (avatar_x, avatar_y), output)
        except Exception as e:
            print(f"Error processing avatar: {e}")

        # Typography
        try:
            # We want a very clean, bold look
            font_name = ImageFont.truetype("arial.ttf", 50)
            font_level_label = ImageFont.truetype("arial.ttf", 30)
            font_level_val = ImageFont.truetype("arial.ttf", 70) # Huge number
            font_xp = ImageFont.truetype("arial.ttf", 25)
        except:
            font_name = ImageFont.load_default()
            font_level_label = ImageFont.load_default()
            font_level_val = ImageFont.load_default()
            font_xp = ImageFont.load_default()

        # Layout
        text_x = 260
        
        # Username - Upper Left relative to text area (With Glitch Effect)
        # Red Shadow
        draw.text((text_x + 2, 45), username, font=font_name, fill=(255, 0, 0, 150))
        # Cyan Shadow
        draw.text((text_x - 2, 45), username, font=font_name, fill=(0, 255, 255, 150))
        # White Main
        draw.text((text_x, 45), username, font=font_name, fill=(255, 255, 255))
        
        # XP - Subtle, below name
        xp_text = f"{xp} / {xp_needed} XP"
        draw.text((text_x, 105), xp_text, font=font_xp, fill=(150, 150, 150))
        
        # Level - Right side, Big and Bold
        level_val_text = str(level)
        w_val = draw.textlength(level_val_text, font=font_level_val)
        
        # Draw "LEVEL" small label above the number
        level_label_text = "LEVEL"
        w_label = draw.textlength(level_label_text, font=font_level_label)
        
        # Align Group Right (margin 50)
        right_margin = 50
        # Determine center of the group for alignment? Or just right align both.
        # Let's right align both to the margin.
        
        # Number
        draw.text((width - right_margin - w_val, 40), level_val_text, font=font_level_val, fill=(255, 255, 255))
        
        # Label (placed above the number or to the left? Let's go with aligned above/left of number for style)
        # Actually in minimal designs, "LEVEL" often sits on top of the number or sidebar.
        # Let's put "LEVEL" vertically centered with name but on right, and number below it?
        # Let's stick to Right Aligned.
        
        draw.text((width - right_margin - w_val - w_label - 15, 65), level_label_text, font=font_level_label, fill=(100, 100, 100)) # Darker grey label for minimal contrast

        # 4. Progress Bar (Thin Gradient)
        bar_x = 260
        bar_y = 150
        bar_w = 580
        bar_h = 6 # Thin line
        
        # Background Line
        draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(40, 40, 40))
        
        # Gradient Fill (Simulated by drawing segments or just a solid color for now, Pillow gradient is complex)
        # Let's do a solid Pink/Purple color for the fill as requested "Purple -> Pink" style vibe
        progress = min(xp / xp_needed, 1.0)
        fill_w = int(bar_w * progress)
        
        if fill_w > 0:
            # We can draw a simple horizontal gradient using a loop if we want premium
            # Or just a nice Color. Let's do a nice Magenta.
            draw.rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], fill=(215, 0, 120)) # Magenta/Pink

        # Save
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

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
