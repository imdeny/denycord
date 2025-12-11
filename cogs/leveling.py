import discord
from discord.ext import commands
from discord import app_commands
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
        await interaction.response.defer(ephemeral=True) 
        
        if not self.selected_level or not self.selected_role:
             return await interaction.followup.send("Please select both a level and a role.", ephemeral=True)
        
        self.cog.bot.db.execute("INSERT OR REPLACE INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?)", 
                  (interaction.guild.id, self.selected_level, self.selected_role.id))
        
        await interaction.followup.send(f"✅ Set **{self.selected_role.name}** for **Level {self.selected_level}**.", ephemeral=True)

    @discord.ui.button(label="View Config", style=discord.ButtonStyle.grey)
    async def view_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        results = self.cog.bot.db.fetchall("SELECT level, role_id FROM level_roles WHERE guild_id = ? ORDER BY level", (interaction.guild.id,))
        
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
        
        result = self.bot.db.fetchone("SELECT xp, level FROM levels WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        
        if result:
            current_xp, current_level = result
            new_xp = current_xp + xp_gain
            
            xp_needed = self.get_xp_for_level(current_level)
            if new_xp >= xp_needed:
                new_level = current_level + 1
                new_xp -= xp_needed
                await message.channel.send(f"🎉 {message.author.mention} has leveled up to **Level {new_level}**!")
                
                # Check for role reward
                role_result = self.bot.db.fetchone("SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?", (guild_id, new_level))
                if role_result:
                    role_id = role_result[0]
                    role = message.guild.get_role(role_id)
                    if role:
                        try:
                            await message.author.add_roles(role)
                            await message.channel.send(f"🏆 You have been awarded the **{role.name}** role!")
                        except discord.Forbidden:
                            pass 

            else:
                new_level = current_level
                
            self.bot.db.execute("UPDATE levels SET xp = ?, level = ? WHERE user_id = ? AND guild_id = ?", 
                      (new_xp, new_level, user_id, guild_id))
        else:
            self.bot.db.execute("INSERT INTO levels (user_id, guild_id, xp, level) VALUES (?, ?, ?, ?)", 
                      (user_id, guild_id, xp_gain, 0))

    @app_commands.command(name="rank", description="Check your current level and XP")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        
        result = self.bot.db.fetchone("SELECT xp, level FROM levels WHERE user_id = ? AND guild_id = ?", (member.id, interaction.guild.id))
        
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
        
        bg_color = (18, 18, 18) 
        image = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(image)
        
        avatar_size = 180
        avatar_x = 40
        avatar_y = 35
        
        try:
            avatar_image = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar_image = avatar_image.resize((avatar_size, avatar_size), resample=Image.Resampling.LANCZOS)
            
            mask = Image.new("L", (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
            
            output = ImageOps.fit(avatar_image, mask.size, centering=(0.5, 0.5))
            output.putalpha(mask)
            
            image.paste(output, (avatar_x, avatar_y), output)
        except Exception as e:
            print(f"Error processing avatar: {e}")

        try:
            font_name = ImageFont.truetype("arial.ttf", 50)
            font_level_label = ImageFont.truetype("arial.ttf", 30)
            font_level_val = ImageFont.truetype("arial.ttf", 70) 
            font_xp = ImageFont.truetype("arial.ttf", 25)
        except:
            font_name = ImageFont.load_default()
            font_level_label = ImageFont.load_default()
            font_level_val = ImageFont.load_default()
            font_xp = ImageFont.load_default()

        text_x = 260
        
        draw.text((text_x + 2, 45), username, font=font_name, fill=(255, 0, 0, 150))
        draw.text((text_x - 2, 45), username, font=font_name, fill=(0, 255, 255, 150))
        draw.text((text_x, 45), username, font=font_name, fill=(255, 255, 255))
        
        xp_text = f"{xp} / {xp_needed} XP"
        draw.text((text_x, 105), xp_text, font=font_xp, fill=(150, 150, 150))
        
        level_val_text = str(level)
        w_val = draw.textlength(level_val_text, font=font_level_val)
        
        level_label_text = "LEVEL"
        w_label = draw.textlength(level_label_text, font=font_level_label)
        
        right_margin = 50
        
        draw.text((width - right_margin - w_val, 40), level_val_text, font=font_level_val, fill=(255, 255, 255))
        draw.text((width - right_margin - w_val - w_label - 15, 65), level_label_text, font=font_level_label, fill=(100, 100, 100))

        bar_x = 260
        bar_y = 150
        bar_w = 580
        bar_h = 6
        
        draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(40, 40, 40))
        
        progress = min(xp / xp_needed, 1.0)
        fill_w = int(bar_w * progress)
        
        if fill_w > 0:
            draw.rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], fill=(215, 0, 120))

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    @app_commands.command(name="leaderboard", description="Shows the top 10 users in the server")
    async def leaderboard(self, interaction: discord.Interaction):
        results = self.bot.db.fetchall("SELECT user_id, level, xp FROM levels WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10", (interaction.guild.id,))
        
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
