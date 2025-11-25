# DenyCord Bot

A comprehensive Discord bot built with Python and discord.py, featuring modular slash commands.

## Features

-   **Slash Commands**: Modern, easy-to-use commands integrated directly into Discord's UI.
-   **Modular Design**: Commands are organized into categories (Essentials, Moderation, Fun).
-   **Easy Setup**: Simple configuration via `.env` file.

## Commands

### Essentials
-   `/ping`: Check the bot's latency with a fun, random location response! 🏓
-   `/info`: View detailed information about the bot.

### Moderation
-   `/kick [member] [reason]`: Kick a user from the server.
-   `/ban [member] [reason]`: Ban a user from the server.
-   `/clear [amount]`: Bulk delete messages in the current channel.

### Fun
-   `/coinflip`: Flip a coin (Heads or Tails).
-   `/roll [sides]`: Roll a dice with a custom number of sides (default 6).

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
