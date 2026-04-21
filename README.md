# DenyCord Bot

A comprehensive Discord bot built with Python and discord.py, featuring modular slash commands.

## Features

-   **Slash Commands**: Modern, easy-to-use commands integrated directly into Discord's UI.
-   **Modular Design**: 17 feature cogs covering moderation, leveling, music, voice, tickets, and more.
-   **Easy Setup**: Simple configuration via `.env` file.
-   **Persistent Storage**: SQLite database with WAL mode — all data survives restarts.

## Commands

### Essentials
-   `/ping`: Check the bot's latency.
-   `/info`: View bot stats (uptime, server count, versions).
-   `/userinfo [member]`: View detailed information about a member.
-   `/serverinfo`: View detailed information about the server.
-   `/avatar [member]`: View a member's avatar in high resolution.
-   `/help`: View all available commands sorted by category.

### Moderation
-   `/kick [member] [reason]`: Kick a user from the server.
-   `/ban [member] [reason]`: Ban a user from the server.
-   `/unban [user_id] [reason]`: Unban a user by their ID.
-   `/timeout [member] [duration] [reason]`: Timeout a member for a specified duration.
-   `/untimeout [member] [reason]`: Remove a timeout from a member.
-   `/lock`: Lock the current channel.
-   `/unlock`: Unlock the current channel.
-   `/slowmode [seconds]`: Set the slowmode delay for the current channel.
-   `/setnick [member] [nickname]`: Change a member's nickname.
-   `/addrole [member] [role]`: Add a role to a member.
-   `/removerole [member] [role]`: Remove a role from a member.
-   `/clear [amount]`: Bulk delete messages in the current channel.
-   `/setup_logs [channel]`: Set a moderation log channel to track bans, kicks, timeouts, and message events.
-   `/warn [member] [reason]`: Issue a warning to a user.
-   `/warnings [member]`: View active warnings for a user.
-   `/clearwarnings [member]`: Clear all warnings for a user.
-   `/delwarn [id]`: Delete a specific warning by its ID.

### Auto-Moderation
Automatically filter messages and protect your server with configurable rules and escalating punishments.

**Core Filters**
-   `/automod_toggle [feature]`: Enable/disable Anti-Invite, Anti-Links, Anti-Caps, Anti-Spam, Anti-Repeat, or Anti-Raid.
-   `/automod_limits [feature] [value]`: Set numeric limits for mentions, emojis, spam rate, repeat count, raid threshold, and minimum account age.
-   `/automod_badwords [action] [word]`: Add, remove, or list banned words (uses word-boundary matching to avoid false positives).

**Punishment System**
-   `/automod_punishment [threshold] [action] [duration]`: Configure what happens at each violation count — Delete, Timeout, Kick, or Ban. Violations escalate automatically per user.
-   `/automod_violations [user]`: Check how many AutoMod violations a user has this session.
-   `/automod_reset_violations [user]`: Reset a user's violation count.

**Exemptions & Logging**
-   `/automod_setup`: View the full current configuration.
-   `/automod_logchannel [channel]`: Set a channel where every AutoMod action is logged with full context.
-   `/automod_exempt [action] [role]`: Exempt roles from all AutoMod filters.
-   `/automod_exempt_channel [action] [channel]`: Exempt entire channels from all filters (e.g. allow links in `#media`).

**Anti-Raid**
-   Detects mass join events and automatically locks all text channels.
-   `/automod_unlock`: Lift an active raid lockdown and restore all channel permissions.

**New Account Filter**
-   Automatically kicks accounts younger than a configured number of days, with a DM explaining why.

### Auto Roles
-   **Automatic Assignment**: Roles assigned to every new member on join.
-   `/autorole_add [role]`: Add a role to be automatically assigned to new members.
-   `/autorole_remove [role]`: Remove an auto role.
-   `/autorole_list`: List all currently configured auto roles.

### Leveling System
-   **XP & Levels**: Earn XP by chatting (15–25 XP per message, 60s cooldown).
-   `/rank [member]`: View a stylized rank card showing level, XP, and progress bar.
-   `/leaderboard`: View the top 10 users by XP in the server.
-   `/setup_rewards`: Configure roles to be automatically awarded at specific levels.

### Welcome System
-   **Automated Greetings**: Send a welcome embed to new members automatically.
-   `/setwelcome [channel]`: Set the channel for welcome messages.
-   `/setwelcomemsg [message]`: Set a custom message using `{user}`, `{server}`, `{member_count}`.
-   `/testwelcome`: Preview the current welcome message configuration.

### AFK System
-   **Away Status**: Let the server know you're away — the bot will notify anyone who pings you.
-   `/afk [reason]`: Set yourself as AFK. Your nickname gets an `[AFK]` prefix automatically.
-   Your AFK status is cleared automatically when you send your next message.

### Reminders
-   **Personal Reminders**: Set reminders delivered via DM or in-channel.
-   `/remind [duration] [message]`: Set a reminder (e.g. `/remind 2h30m Check the oven`).
-   `/reminders_list`: View all your active reminders.
-   `/reminders_cancel [id]`: Cancel a reminder by its ID.
-   Supports flexible duration strings (e.g. `1h`, `30m`, `2d12h`). Max 5 active reminders per user.

### Birthdays
-   **Automatic Announcements**: Celebrates member birthdays with a message and a temporary role.
-   `/birthday_setup [channel] [role]`: Configure the announcement channel and birthday role.
-   `/birthday_set [month] [day]`: Register your birthday.
-   `/birthday_remove`: Remove your birthday from the server.
-   `/birthday_list`: View all registered birthdays in the server.
-   `/birthday_check`: Manually trigger the birthday check (admin).

### Stat Channels
-   **Live Statistics**: Voice channels that display live server stats, updating every 10 minutes.
-   `/stats_setup [type]`: Create a stat channel. Types: Members, Humans, Bots, Server Boosts.
-   `/stats_remove [type]`: Remove a stat channel.

### VoiceMaster / Join to Create
-   **Automatic Channel Management**: Join the hub channel to instantly get your own private voice channel. It deletes itself when empty.
-   **Control Panel**: Buttons let you Lock/Unlock, Rename, Set a user limit, Permit/Kick users, and Claim ownership.
-   **Dynamic Ownership**: If the owner leaves, any user can claim the channel.
-   `/voice_setup`: Create the Join to Create hub channel and category.
-   `/voice_setname [name]`: Set your preferred default channel name (supports `{user}` placeholder).

### Reaction Roles
-   **Self-Assignment**: Users assign roles to themselves by reacting to a message.
-   `/rr_add [message_id] [role] [emoji]`: Add a reaction role to a message.
-   `/rr_remove [message_id] [emoji]`: Remove a reaction role.
-   `/rr_list`: List all active reaction roles in the current channel.

### Giveaways
-   `/gstart [duration] [winners] [prize]`: Start a giveaway (e.g. `/gstart 10m 1 Nitro`).
-   `/gend [message_id]`: End a giveaway immediately and pick winners.
-   `/greroll [message_id]`: Pick a new winner for a finished giveaway.

### Ticket System
-   **One-Click Support**: Members open tickets with a button; the bot creates a private channel automatically.
-   `/ticket_setup`: Creates the ticket category, panel, and log channel.
-   `/ticket_add [user]`: Grant a user access to a ticket.
-   `/ticket_remove [user]`: Remove a user's access from a ticket.
-   **Transcripts**: Closing a ticket generates an HTML transcript sent to the log channel and DM'd to the user.
-   **Templates**: Pre-written responses admins can configure for common ticket types.
    -   `/ticket_template_add [name] [content]`: Add a response template.
    -   `/ticket_template_delete [name]`: Delete a template.
    -   `/ticket_template_list`: List all templates.

### Music
-   `/play [query]`: Play a song from YouTube by search or URL.
-   `/pause`: Pause the current song.
-   `/resume`: Resume playback.
-   `/stop`: Stop playback, clear the queue, and disconnect.
-   `/skip`: Skip the current song.
-   `/queue`: View the current song queue.
-   `/queue_remove [position]`: Remove a song from the queue by position.
-   `/queue_move [from] [to]`: Move a song to a different position in the queue.
-   `/nowplaying`: View details about the currently playing song.
-   `/join`: Join your voice channel.
-   `/leave`: Disconnect from the voice channel.

### Server Backup
-   **Full Guild Backup**: Backs up roles, channels, permissions, emojis, and all bot configuration.
-   `/backup_create`: Creates a backup and DMs it to you as a JSON file.
-   `/backup_restore [attachment]`: Preview and then restore a backup (roles, categories, channels, bot settings).
-   `/backup_schedule [channel]`: Automatically post an hourly backup to a channel.
-   `/backup_unschedule`: Stop automatic backups.

---

## Setup

1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd denycord
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment**:
    -   Create a `.env` file in the root directory.
    -   Add your Discord Bot Token:
        ```env
        DISCORD_TOKEN=your_token_here
        # Optional: Add DEV_GUILD_ID for faster slash command testing
        DEV_GUILD_ID=your_guild_id
        ```

4.  **Run the Bot**:
    ```bash
    python bot.py
    ```
    - The bot will automatically create `bot_database.db` and initialize all necessary tables.
    - FFmpeg is required for music. Ensure it is installed and accessible in your PATH.

### Docker Setup

Run the bot using Docker — handles all dependencies including FFmpeg automatically.

1.  **Prerequisites**: Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2.  **Run**:
    ```bash
    docker-compose up -d
    ```
3.  **Logs**: `docker-compose logs -f`
4.  **Stop**: `docker-compose down`

## Contributing

Feel free to submit issues or pull requests to improve the bot!