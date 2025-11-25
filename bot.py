import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    print("Error: DISCORD_TOKEN not found in .env file.")
    print("Please create a .env file and add your token: DISCORD_TOKEN=your_token_here")
    exit(1)

# Setup intents
intents = discord.Intents.default()
intents.message_content = True

# Setup bot
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='ping')
async def ping(ctx):
    await ctx.send('Pong!')

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("Error: Invalid Discord Token. Please check your .env file.")
