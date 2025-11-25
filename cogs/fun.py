import discord
from discord.ext import commands
from discord import app_commands
import random

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="coinflip", description="Flips a coin")
    async def coinflip(self, interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        await interaction.response.send_message(f"It's **{result}**!")

    @app_commands.command(name="roll", description="Rolls a dice")
    @app_commands.describe(sides="Number of sides on the dice (default 6)")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        if sides < 2:
            await interaction.response.send_message("A dice must have at least 2 sides.", ephemeral=True)
            return
        
        result = random.randint(1, sides)
        await interaction.response.send_message(f"You rolled a **{result}** (1-{sides})!")

async def setup(bot):
    await bot.add_cog(Fun(bot))
