# DenyCord Bot

A comprehensive Discord bot built with Python and discord.py, featuring modular slash commands.

## Features

-   **Slash Commands**: Modern, easy-to-use commands integrated directly into Discord's UI.
-   **Modular Design**: Commands are organized into categories (Essentials, Moderation, Fun).
-   **Easy Setup**: Simple configuration via `.env` file.

## Commands

### Essentials
-   `/ping`: Check the bot's latency with a fun, random location response! 🏓
-   `/info`: View bot stats (uptime, server count, versions).
-   `/userinfo [member]`: View detailed information about a member.
-   `/serverinfo`: View detailed information about the server.
-   `/avatar [member]`: View a member's avatar in high resolution.
-   `/help`: View a list of all available commands sorted by category.

### Moderation
-   `/kick [member] [reason]`: Kick a user from the server.
-   `/ban [member] [reason]`: Ban a user from the server.
-   `/unban [user_id] [reason]`: Unban a user by their ID.
-   `/timeout [member] [duration] [reason]`: Timeout a member for a specified duration (in minutes).
-   `/untimeout [member] [reason]`: Remove a timeout from a member.
-   `/lock`: Lock the current channel (prevent sending messages).
-   `/unlock`: Unlock the current channel.
-   `/slowmode [seconds]`: Set the slowmode delay for the current channel.
-   `/setnick [member] [nickname]`: Change a member's nickname.
-   `/addrole [member] [role]`: Add a role to a member.
-   `/removerole [member] [role]`: Remove a role from a member.
-   `/clear [amount]`: Bulk delete messages in the current channel.
-   `/setup_logs [channel]`: Setup a moderation log channel to track bans, kicks, timeouts, and message events.
-   `/warn [member] [reason]`: Warn a user and log it.
-   `/warnings [member]`: View active warnings for a user.
-   `/clearwarnings [member]`: Clear all warnings for a user.
-   `/delwarn [id]`: Delete a specific warning by its ID.

### Fun
-   `/coinflip`: Flip a coin (Heads or Tails).
-   `/roll [sides]`: Roll a dice with a custom number of sides (default 6).
-   `/8ball [question]`: Ask the magic 8-ball a question.
-   `/rps [choice]`: Play Rock, Paper, Scissors against the bot.
-   `/choose [options]`: Let the bot choose from a list of comma-separated options.
-   `/poll [question] [options]`: Create a poll with up to 10 options.

### Leveling System
-   **XP & Levels**: Gain XP by chatting in text channels.
-   `/rank [member]`: Check your current level, XP, and progress.
-   `/rank [member]`: Check your current level, XP, and progress.
-   `/leaderboard`: View the top 10 users with the most XP in the server.
-   `/setup_rewards`: Configure role rewards to be automatically given at specific levels.

### Welcome System
-   **Automated Greetings**: Send a stylish welcome embed to new members.
-   `/setwelcome [channel]`: Set the channel where welcome messages will be sent.
-   `/setwelcomemsg [message]`: Set a custom welcome message using variables `{user}`, `{server}`, `{member_count}`.
-   `/testwelcome`: Test the welcome message configuration.

### VoiceMaster / Join to Create
-   **Automatic Channel Management**: Join the "Join to Create" channel to get your own temporary voice channel. It deletes itself when empty.
-   **Control Panel**: A menu with buttons appears in your temporary channel's chat to easily Lock, Unlock, Rename, Limit, and Claim your channel.
-   **Dynamic Ownership**: If a channel owner leaves, another user can click the "Claim" button to become the new host.
-   `/voice_setup`: (Admin) Creates the "Join to Create" hub channel and category.
-   `/voice_setname [name]`: Set your preferred default name for your temporary channels (supports `{user}` placeholder).

### Reaction Roles
-   **Self-Assignment**: Allow users to assign roles to themselves by reacting to a message.
-   `/rr add [message_id] [role] [emoji]`: Add a reaction role to a message.
-   `/rr remove [message_id] [emoji]`: Remove a reaction role from a message.
-   `/rr list`: List all active reaction roles in the current channel.

### Giveaways
-   **Host Giveaways**: Easily start and manage giveaways in your server.
-   `/gstart [duration] [winners] [prize]`: Start a new giveaway (e.g. `/gstart 10m 1 Nitro`).
-   `/gend [message_id]`: End a giveaway immediately.
-   `/greroll [message_id]`: Pick a new winner for a finished giveaway.

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
        ```

4.  **Run the Bot**:
    ```bash
    python bot.py
    ```

## Contributing

Feel free to submit issues or pull requests to improve the bot!
