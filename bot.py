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

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        # Load cogs
        initial_extensions = [
            'cogs.essentials',
            'cogs.moderation',
            'cogs.fun'
        ]
        
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                print(f'Loaded extension {extension}')
            except Exception as e:
                print(f'Failed to load extension {extension}.', e)

        # Sync commands globally
        # Note: Global sync can take up to an hour. For development, sync to a specific guild.
        try:
            synced = await self.tree.sync()
            print(f'Synced {len(synced)} command(s) globally')
        except Exception as e:
            print(f'Failed to sync commands: {e}')

    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')

bot = MyBot()

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("Error: Invalid Discord Token. Please check your .env file.")
