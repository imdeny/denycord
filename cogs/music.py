import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import datetime
import os
import shutil

# FFmpeg setup
def ensure_ffmpeg():
    if shutil.which("ffmpeg") is None:
        # Helper to find and add ffmpeg to path if not present via WinGet or common locations
        # This is a fallback attempt for Windows users
        local_app_data = os.getenv('LOCALAPPDATA')
        if local_app_data:
            common_paths = [
                 os.path.join(local_app_data, r"Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin"),
                 r"C:\ffmpeg\bin"
            ]
            for path in common_paths:
                if os.path.exists(path) and path not in os.environ["PATH"]:
                    print(f"Adding FFmpeg to PATH: {path}")
                    os.environ["PATH"] += ";" + path
                    break

ensure_ffmpeg()

# Output logging options for yt-dlp
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, requester, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.requester = requester
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.thumbnail = data.get('thumbnail')
        self.uploader = data.get('uploader')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, requester=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data, requester=requester)

class MusicPlayer:
    def __init__(self, ctx, cog):
        self.bot = ctx.bot
        self.guild = ctx.guild
        self.channel = ctx.channel
        self.cog = cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None  # Now playing message
        self.volume = .5
        self.current = None
        self.start_time = None

    async def player_loop(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()

            try:
                # Wait for the next song.
                async with asyncio.timeout(300): # 5 minutes timeout
                     source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self.guild)

            if not isinstance(source, YTDLSource):
                # Should not happen if type checking is good, but safety net
                pass

            self.current = source
            self.start_time = datetime.datetime.now(datetime.timezone.utc)
            
            try:
                self.guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
                await self.channel.send(embed=self.create_np_embed(source))
                await self.next.wait()
            except Exception as e:
                print(f"Error playing song: {e}")
                
            # Cleanup
            self.current = None
            source.cleanup()

    def create_np_embed(self, source):
        embed = discord.Embed(
            title="🎶 Now Playing", 
            description=f"[{source.title}]({source.url})", 
            color=discord.Color.from_rgb(75, 139, 190)
        )
        
        duration = source.duration
        if duration:
            try:
                # Calculate progress logic for future polling/updates if we wanted dynamic updating,
                # but for static embed start, it is 0.
                total_blocks = 15
                bar = "🔘" + "▬" * (total_blocks)
                time_str = f"0:00 / {str(datetime.timedelta(seconds=duration))}"
                embed.add_field(name="Progress", value=f"`{bar}`\n`{time_str}`", inline=False)
            except Exception:
                 embed.add_field(name="Duration", value=str(datetime.timedelta(seconds=duration)), inline=False)
        else:
             embed.add_field(name="Duration", value="Live / Unknown", inline=False)

        embed.add_field(name="Requested by", value=source.requester.mention if source.requester else "Unknown", inline=True)
        if source.thumbnail:
            embed.set_thumbnail(url=source.thumbnail)
            
        return embed

    def destroy(self, guild):
        return self.bot.loop.create_task(self.cog.cleanup(guild))

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.players[guild.id]
        except KeyError:
            pass

    def get_player(self, ctx):
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx, self)
            self.players[ctx.guild.id] = player
            self.bot.loop.create_task(player.player_loop())
        
        return player

    @app_commands.command(name="play", description="Plays a song from YouTube (Search or URL)")
    @app_commands.describe(query="The search term or URL")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        
        if not interaction.user.voice:
            return await interaction.followup.send("You are not connected to a voice channel.")

        channel = interaction.user.voice.channel
        
        if interaction.guild.voice_client is None:
            await channel.connect()
        elif interaction.guild.voice_client.channel != channel:
             return await interaction.followup.send("I am already in another voice channel.")

        player = self.get_player(await self.bot.get_context(interaction))

        try:
            source = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True, requester=interaction.user)
        except Exception as e:
            return await interaction.followup.send(f'An error occurred while processing this request: {e}')

        await player.queue.put(source)
        await interaction.followup.send(f'Queued **{source.title}**')

    @app_commands.command(name="stop", description="Stops playback and clears the queue")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return await interaction.response.send_message("I am not currently playing anything.", ephemeral=True)

        await self.cleanup(interaction.guild)
        await interaction.response.send_message("⏹️ Stopped playback and disconnected due to user request.")

    @app_commands.command(name="skip", description="Skips the current song")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return await interaction.response.send_message("I am not currently playing anything.", ephemeral=True)

        if vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ Skipped.")
        else:
            await interaction.response.send_message("Nothing is playing to skip.", ephemeral=True)

    @app_commands.command(name="pause", description="Pauses the player")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resumes the player")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("Player is not paused.", ephemeral=True)

    @app_commands.command(name="queue", description="Shows the current queue")
    async def queue_info(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            return await interaction.response.send_message("I am not connected to a voice channel.", ephemeral=True)

        player = self.get_player(await self.bot.get_context(interaction))
        if player.queue.empty():
            return await interaction.response.send_message("Queue is empty.", ephemeral=True)

        upcoming = list(player.queue._queue)
        
        fmt = '\n'.join([f'**{i + 1}.** {_source.title}' for i, _source in enumerate(upcoming[:10])])
        embed = discord.Embed(title=f'Queue ({len(upcoming)} songs)', description=fmt, color=discord.Color.green())
        if len(upcoming) > 10:
            embed.set_footer(text=f"And {len(upcoming) - 10} more...")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Shows the currently playing song")
    async def now_playing(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            return await interaction.response.send_message("I am not connected.", ephemeral=True)

        player = self.get_player(await self.bot.get_context(interaction))
        if not player.current:
            return await interaction.response.send_message("Nothing is playing.", ephemeral=True)

        # Re-calc progress specifically for this command
        source = player.current
        embed = player.create_np_embed(source)
        # Update progress in embed
        if source.duration:
             try:
                current_time = datetime.datetime.now(datetime.timezone.utc)
                elapsed = (current_time - player.start_time).total_seconds() if player.start_time else 0
                elapsed = min(elapsed, source.duration)
                
                total_blocks = 15
                filled_blocks = int((elapsed / source.duration) * total_blocks)
                
                bar = "▬" * filled_blocks + "🔘" + "▬" * (total_blocks - filled_blocks)
                time_str = f"{str(datetime.timedelta(seconds=int(elapsed)))} / {str(datetime.timedelta(seconds=source.duration))}"
                
                # Replace the field
                embed.set_field_at(0, name="Progress", value=f"`{bar}`\n`{time_str}`", inline=False)
             except:
                 pass

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="join", description="Joins your voice channel")
    async def join(self, interaction: discord.Interaction):
        if not interaction.user.voice:
             return await interaction.response.send_message("You are not in a voice channel.", ephemeral=True)
        
        channel = interaction.user.voice.channel
        await channel.connect()
        await interaction.response.send_message(f"Joined {channel.mention}")

    @app_commands.command(name="leave", description="Leaves the voice channel")
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await self.cleanup(interaction.guild)
            await interaction.response.send_message("Disconnected.")
        else:
            await interaction.response.send_message("I am not in a voice channel.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Music(bot))
