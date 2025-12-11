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
intents.members = True

class MyBot(commands.AutoShardedBot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        # Load cogs
        initial_extensions = [
            'cogs.essentials',
            'cogs.moderation',
            'cogs.fun',
            'cogs.voice',
            'cogs.leveling',
            'cogs.welcome',
            'cogs.reaction_roles',
            'cogs.giveaways',
            'cogs.music',
            'cogs.automod'
        ]
        
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                print(f'Loaded extension {extension}')
            except Exception as e:
                print(f'Failed to load extension {extension}.', e)

        # Sync commands globally and to the dev guild
        # Note: Global sync can take up to an hour. For development, sync to a specific guild.
        try:
            # Sync to Dev Guild for immediate testing
            dev_guild_id = os.getenv('DEV_GUILD_ID')
            if dev_guild_id:
                DEV_GUILD = discord.Object(id=int(dev_guild_id))
                self.tree.copy_global_to(guild=DEV_GUILD)
                await self.tree.sync(guild=DEV_GUILD)
                print(f'Synced commands to Dev Guild (ID: {DEV_GUILD.id})')
            else:
                print("DEV_GUILD_ID not set in .env, skipping guild sync.")
            
            # Sync Globally
            synced = await self.tree.sync()
            print(f'Synced {len(synced)} command(s) globally')
        except Exception as e:
            print(f'Failed to sync commands: {e}')

    async def on_ready(self):
        await self.change_presence(activity=discord.CustomActivity(name="Watching channels - /help"))
        print(f'{self.user} has connected to Discord!')
        print(f'Connected to {len(self.guilds)} server(s).')

bot = MyBot()

@bot.command()
async def sync(ctx):
    print("Syncing commands...")
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"Synced {len(synced)} commands globally.")
        print(f"Synced {len(synced)} commands globally.")
    except Exception as e:
        await ctx.send(f"Failed to sync: {e}")
        print(f"Failed to sync: {e}")

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("Error: Invalid Discord Token. Please check your .env file.")
