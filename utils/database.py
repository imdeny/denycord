import sqlite3
import logging
import os
import json

class DatabaseManager:
    def __init__(self, db_name="bot_database.db"):
        self.db_name = db_name
        self.logger = logging.getLogger("DatabaseManager")
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_db(self):
        """Initializes all necessary tables for the bot."""
        conn = self.get_connection()
        c = conn.cursor()
        
        # --- Core/General ---
        
        # --- Moderation ---
        c.execute('''CREATE TABLE IF NOT EXISTS mod_logs
                     (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS warnings
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, guild_id INTEGER, 
                      moderator_id INTEGER, reason TEXT, timestamp TIMESTAMP)''')

        # --- Leveling ---
        c.execute('''CREATE TABLE IF NOT EXISTS levels
                     (user_id INTEGER, guild_id INTEGER, xp INTEGER, level INTEGER,
                      PRIMARY KEY (user_id, guild_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS level_roles
                     (guild_id INTEGER, level INTEGER, role_id INTEGER,
                      PRIMARY KEY (guild_id, level))''')

        # --- Welcome ---
        c.execute('''CREATE TABLE IF NOT EXISTS welcome_config
                     (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
        try:
            c.execute("ALTER TABLE welcome_config ADD COLUMN message_text TEXT")
        except sqlite3.OperationalError:
            pass

        # --- Reaction Roles ---
        c.execute('''CREATE TABLE IF NOT EXISTS reaction_roles
                     (message_id INTEGER, role_id INTEGER, emoji TEXT, channel_id INTEGER,
                      PRIMARY KEY (message_id, emoji))''')
        try:
            c.execute("ALTER TABLE reaction_roles ADD COLUMN channel_id INTEGER")
        except sqlite3.OperationalError:
            pass

        # --- Giveaways ---
        c.execute('''CREATE TABLE IF NOT EXISTS giveaways
                     (message_id INTEGER PRIMARY KEY, channel_id INTEGER, 
                      prize TEXT, end_time TIMESTAMP, winners_count INTEGER, status TEXT)''')
        
        # --- Automod ---
        c.execute('''CREATE TABLE IF NOT EXISTS automod_settings
                     (guild_id INTEGER PRIMARY KEY, 
                      bad_words TEXT, 
                      anti_invite INTEGER, 
                      anti_links INTEGER, 
                      anti_caps INTEGER, 
                      max_mentions INTEGER, 
                      max_emojis INTEGER, 
                      exempt_roles TEXT)''')
        
        # --- Voice Config ---
        # Storing guild config (hub_id) and user settings. 
        # Using a simplistic Key-Value text storage for json blobs might be easiest if schema varies, 
        # but let's try to structure it.
        # Actually, since voice_config.json stores strictly nested data, let's make two tables.
        
        c.execute('''CREATE TABLE IF NOT EXISTS voice_hubs
                     (guild_id INTEGER PRIMARY KEY, hub_id INTEGER)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS voice_user_settings
                     (user_id INTEGER PRIMARY KEY, name TEXT)''')

        conn.commit()
        conn.close()
        self.logger.info("Database initialized and tables verified.")

    def execute(self, query, params=(), commit=True):
        """Executes a simple query."""
        conn = self.get_connection()
        c = conn.cursor()
        try:
            c.execute(query, params)
            if commit:
                conn.commit()
            return c
        except Exception as e:
            self.logger.error(f"Database error executing {query}: {e}")
            raise
        finally:
            conn.close()

    def fetchone(self, query, params=()):
        conn = self.get_connection()
        c = conn.cursor()
        try:
            c.execute(query, params)
            return c.fetchone()
        finally:
            conn.close()

    def fetchall(self, query, params=()):
        conn = self.get_connection()
        c = conn.cursor()
        try:
            c.execute(query, params)
            return c.fetchall()
        finally:
            conn.close()
