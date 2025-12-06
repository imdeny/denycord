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

    @app_commands.command(name="poll", description="Creates a simple poll")
    @app_commands.describe(question="The question for the poll", options="Options separated by commas")
    async def poll(self, interaction: discord.Interaction, question: str, options: str):
        choice_list = [x.strip() for x in options.split(",") if x.strip()]
        
        if len(choice_list) < 2 or len(choice_list) > 10:
             return await interaction.response.send_message("Please provide between 2 and 10 options separated by commas.", ephemeral=True)
             
        # Emojis for 1-10
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        description = []
        for i, choice in enumerate(choice_list):
            description.append(f"{emojis[i]} {choice}")
            
        embed = discord.Embed(title=f"📊 {question}", description="\n".join(description), color=discord.Color.blue())
        embed.set_footer(text=f"Poll created by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        
        for i in range(len(choice_list)):
            await message.add_reaction(emojis[i])

async def setup(bot):
    await bot.add_cog(Fun(bot))
