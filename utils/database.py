import sqlite3
import logging

class DatabaseManager:
    def __init__(self, db_name="bot_database.db"):
        self.db_name = db_name
        self.logger = logging.getLogger("DatabaseManager")
        self._conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self.init_db()

    def init_db(self):
        """Initializes all necessary tables for the bot."""
        c = self._conn.cursor()

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
                      exempt_roles TEXT,
                      log_channel_id INTEGER,
                      anti_spam INTEGER DEFAULT 0,
                      spam_count INTEGER DEFAULT 5,
                      spam_seconds INTEGER DEFAULT 5,
                      min_account_age INTEGER DEFAULT 0,
                      anti_raid INTEGER DEFAULT 0,
                      raid_count INTEGER DEFAULT 10,
                      raid_seconds INTEGER DEFAULT 10,
                      anti_repeat INTEGER DEFAULT 0,
                      repeat_count INTEGER DEFAULT 3,
                      punishments TEXT,
                      exempt_channels TEXT)''')
        # Migrate existing installs — add new columns if missing
        for col, definition in [
            ("log_channel_id", "INTEGER"),
            ("anti_spam", "INTEGER DEFAULT 0"),
            ("spam_count", "INTEGER DEFAULT 5"),
            ("spam_seconds", "INTEGER DEFAULT 5"),
            ("min_account_age", "INTEGER DEFAULT 0"),
            ("anti_raid", "INTEGER DEFAULT 0"),
            ("raid_count", "INTEGER DEFAULT 10"),
            ("raid_seconds", "INTEGER DEFAULT 10"),
            ("anti_repeat", "INTEGER DEFAULT 0"),
            ("repeat_count", "INTEGER DEFAULT 3"),
            ("punishments", "TEXT"),
            ("exempt_channels", "TEXT"),
        ]:
            try:
                c.execute(f"ALTER TABLE automod_settings ADD COLUMN {col} {definition}")
            except Exception:
                pass

        # --- Tickets ---
        c.execute('''CREATE TABLE IF NOT EXISTS ticket_settings
                     (guild_id INTEGER PRIMARY KEY, active_category_id INTEGER,
                      archive_category_id INTEGER, panel_channel_id INTEGER,
                      transcript_channel_id INTEGER, ticket_count INTEGER DEFAULT 0)''')
        try:
            c.execute("ALTER TABLE ticket_settings ADD COLUMN transcript_channel_id INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE ticket_settings ADD COLUMN ticket_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        c.execute('''CREATE TABLE IF NOT EXISTS tickets
                     (channel_id INTEGER PRIMARY KEY, guild_id INTEGER,
                      owner_id INTEGER, status TEXT, created_at TIMESTAMP)''')

        # --- Auto-Mod Actions ---
        c.execute('''CREATE TABLE IF NOT EXISTS automod_actions
                     (guild_id INTEGER PRIMARY KEY, warn_threshold INTEGER,
                      action TEXT, duration_minutes INTEGER)''')

        # --- Ticket Templates ---
        c.execute('''CREATE TABLE IF NOT EXISTS ticket_templates
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER,
                      name TEXT, content TEXT, UNIQUE(guild_id, name))''')

        # --- Stats Channels ---
        c.execute('''CREATE TABLE IF NOT EXISTS stats_channels
                     (guild_id INTEGER, stat_type TEXT, channel_id INTEGER,
                      PRIMARY KEY (guild_id, stat_type))''')

        # --- Auto Roles ---
        c.execute('''CREATE TABLE IF NOT EXISTS auto_roles
                     (guild_id INTEGER, role_id INTEGER,
                      PRIMARY KEY (guild_id, role_id))''')

        # --- Voice ---
        c.execute('''CREATE TABLE IF NOT EXISTS voice_hubs
                     (guild_id INTEGER PRIMARY KEY, hub_id INTEGER)''')

        c.execute('''CREATE TABLE IF NOT EXISTS voice_user_settings
                     (user_id INTEGER PRIMARY KEY, name TEXT)''')

        # --- Backup ---
        c.execute('''CREATE TABLE IF NOT EXISTS backup_settings
                     (guild_id INTEGER PRIMARY KEY, channel_id INTEGER,
                      interval_hours INTEGER, last_backup_at REAL)''')

        # --- Reminders ---
        c.execute('''CREATE TABLE IF NOT EXISTS reminders
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER, guild_id INTEGER, channel_id INTEGER,
                      message TEXT, fire_at REAL, deliver_dm INTEGER)''')

        # --- AFK ---
        c.execute('''CREATE TABLE IF NOT EXISTS afk
                     (user_id INTEGER, guild_id INTEGER, reason TEXT, timestamp REAL,
                      PRIMARY KEY (user_id, guild_id))''')

        # --- Birthdays ---
        c.execute('''CREATE TABLE IF NOT EXISTS birthday_settings
                     (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, role_id INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS birthdays
                     (user_id INTEGER, guild_id INTEGER, month INTEGER, day INTEGER,
                      PRIMARY KEY (user_id, guild_id))''')

        self._conn.commit()
        self.logger.info("Database initialized and tables verified.")

    def execute(self, query, params=(), commit=True):
        """Executes a query and returns the cursor. The cursor remains valid."""
        c = self._conn.cursor()
        try:
            c.execute(query, params)
            if commit:
                self._conn.commit()
            return c
        except Exception as e:
            self._conn.rollback()
            self.logger.error(f"Database error executing {query}: {e}")
            raise

    def fetchone(self, query, params=()):
        c = self._conn.cursor()
        c.execute(query, params)
        return c.fetchone()

    def fetchall(self, query, params=()):
        c = self._conn.cursor()
        c.execute(query, params)
        return c.fetchall()
