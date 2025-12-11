import sys
import os
import asyncio

# Add current dir to path
sys.path.append(os.getcwd())

try:
    print("1. Testing imports...")
    from utils.database import DatabaseManager
    import discord
    from discord.ext import commands
    print("   Imports successful.")

    print("2. Testing DatabaseManager initialization...")
    db = DatabaseManager()
    print("   DatabaseManager initialized and tables created.")

    print("3. Testing Cog imports...")
    from cogs import automod, voice, music, leveling, moderation, welcome, reaction_roles, giveaways, essentials, fun
    print("   All Cogs imported successfully.")

    print("\n✅ Verification passed!")
except Exception as e:
    print(f"\n❌ Verification failed: {e}")
    import traceback
    traceback.print_exc()
