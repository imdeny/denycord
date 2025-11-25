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

    @app_commands.command(name="8ball", description="Ask the magic 8-ball a question")
    @app_commands.describe(question="The question to ask")
    async def eightball(self, interaction: discord.Interaction, question: str):
        responses = [
            "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes - definitely.",
            "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.",
            "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
            "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
            "Don't count on it.", "My reply is no.", "My sources say no.", "Outlook not so good.",
            "Very doubtful."
        ]
        response = random.choice(responses)
        await interaction.response.send_message(f"🎱 **Question:** {question}\n**Answer:** {response}")

    @app_commands.command(name="rps", description="Play Rock, Paper, Scissors")
    @app_commands.describe(choice="Your choice")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Rock", value="rock"),
        app_commands.Choice(name="Paper", value="paper"),
        app_commands.Choice(name="Scissors", value="scissors")
    ])
    async def rps(self, interaction: discord.Interaction, choice: app_commands.Choice[str]):
        user_choice = choice.value
        bot_choice = random.choice(["rock", "paper", "scissors"])
        
        result = "It's a tie!"
        if (user_choice == "rock" and bot_choice == "scissors") or \
           (user_choice == "paper" and bot_choice == "rock") or \
           (user_choice == "scissors" and bot_choice == "paper"):
            result = "You win!"
        elif user_choice != bot_choice:
            result = "I win!"
            
        await interaction.response.send_message(f"You chose **{user_choice}**. I chose **{bot_choice}**.\n{result}")

    @app_commands.command(name="choose", description="Chooses between multiple options")
    @app_commands.describe(options="Options separated by commas")
    async def choose(self, interaction: discord.Interaction, options: str):
        choices = [x.strip() for x in options.split(",") if x.strip()]
        if len(choices) < 2:
            await interaction.response.send_message("Please provide at least two options separated by commas.", ephemeral=True)
            return
        
        choice = random.choice(choices)
        await interaction.response.send_message(f"I choose... **{choice}**!")

async def setup(bot):
    await bot.add_cog(Fun(bot))
