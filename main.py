import nextcord
from nextcord import Interaction, SlashOption, ChannelType
from nextcord.abc import GuildChannel
from nextcord.ext import commands
from wavelink.ext import spotify
import wavelink
import datetime

bot = commands.Bot(command_prefix='!')

class ControlPanel(nextcord.ui.View):
    def __init__(self, vc, ctx):
        super().__init__()
        self.vc = vc
        self.ctx = ctx
    
    @nextcord.ui.button(label="Resume/Pause", style=nextcord.ButtonStyle.blurple)
    async def resume_and_pause(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        if not interaction.user == self.ctx.author:
            return await interaction.response.send_message("You can't do that. run the command yourself to use these buttons", ephemeral=True)
        for child in self.children:
            child.disabled = False
        if self.vc.is_paused():
            await self.vc.resume()
            await interaction.message.edit(content="Resumed", view=self)
        else:
            await self.vc.pause()
            await interaction.message.edit(content="Paused", view=self)

    @nextcord.ui.button(label="Queue", style=nextcord.ButtonStyle.blurple)
    async def queue(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        if not interaction.user == self.ctx.author:
            return await interaction.response.send_message("You can't do that. run the command yourself to use these buttons", ephemeral=True)
        for child in self.children:
            child.disabled = False
        button.disabled = True
        if self.vc.queue.is_empty:
            return await interaction.response.send_message("the queue is empty smh", ephemeral=True)
    
        em = nextcord.Embed(title="Queue")
        queue = self.vc.queue.copy()
        songCount = 0

        for song in queue:
            songCount += 1
            em.add_field(name=f"Song Num {str(songCount)}", value=f"`{song}`")
        await interaction.message.edit(embed=em, view=self)
    
    @nextcord.ui.button(label="Skip", style=nextcord.ButtonStyle.blurple)
    async def skip(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        if not interaction.user == self.ctx.author:
            return await interaction.response.send_message("You can't do that. run the command yourself to use these buttons", ephemeral=True)
        for child in self.children:
            child.disabled = False
        button.disabled = True
        if self.vc.queue.is_empty:
            return await interaction.response.send_message("the queue is empty smh", ephemeral=True)

        try:
            next_song = self.vc.queue.get()
            await self.vc.play(next_song)
            await interaction.message.edit(content=f"Now Playing `{next_song}`", view=self)
        except Exception:
            return await interaction.response.send_message("The queue is empty!", ephemeral=True)
    
    @nextcord.ui.button(label="Disconnect", style=nextcord.ButtonStyle.red)
    async def disconnect(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        if not interaction.user == self.ctx.author:
            return await interaction.response.send_message("You can't do that. run the command yourself to use these buttons", ephemeral=True)
        for child in self.children:
            child.disabled = True
        await self.vc.disconnect()
        await interaction.message.edit(content="Disconnect :P", view=self)
        
@bot.event
async def on_ready():
    print("Bot is up and ready!")
    bot.loop.create_task(node_connect())
    
@bot.event
async def on_wavelink_node_ready(node: wavelink.Node):
    print(f"Node {node.identifier} is ready!")

async def node_connect():
    await bot.wait_until_ready()
    await wavelink.NodePool.create_node(bot=bot, host='host', port=443, password='node pswd', https=True, spotify_client=spotify.SpotifyClient(client_id="spotify client ID", client_secret="spotify client secret"))

@bot.event
async def on_wavelink_track_end(player: wavelink.Player, track: wavelink.YouTubeTrack, reason):
    try:
        ctx = player.ctx
        vc: player = ctx.voice_client
        
    except nextcord.HTTPException:
        interaction = player.interaction
        vc: player = interaction.guild.voice_client
    
    if vc.loop:
        return await vc.play(track)
    
    if vc.queue.is_empty:
        return await vc.disconnect()

    next_song = vc.queue.get()
    await vc.play(next_song)
    try:
        await ctx.send(f"Now playing: {next_song.title}")
    except nextcord.HTTPException:
        await interaction.send(f"Now playing: {next_song.title}")

@bot.command()
async def panel(ctx: commands.Context):
    if not ctx.voice_client:
        vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
    elif not getattr(ctx.author.voice, "channel", None):
        return await ctx.send("join a voice channel first lol")
    else:
        vc: wavelink.Player = ctx.voice_client
    if not vc.is_playing():
        return await ctx.send("first play some music")
    
    em = nextcord.Embed(title="Music Panel", description="control the bot by clicking on the buttons below")
    view = ControlPanel(vc, ctx)
    await ctx.send(embed=em, view=view)

@bot.command()
async def play(ctx: commands.Context, *, search: wavelink.YouTubeTrack):
    if not ctx.voice_client:
        vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
    elif not getattr(ctx.author.voice, "channel", None):
        return await ctx.send("join a voice channel first lol")
    else:
        vc: wavelink.Player = ctx.voice_client
        
    if vc.queue.is_empty and not vc.is_playing():
        await vc.play(search)
        await ctx.send(f'Playing `{search.title}`')          
    else:
        await vc.queue.put_wait(search)
        await ctx.send(f'Added `{search.title}` to the queue...')
    vc.ctx = ctx
    try:
        if vc.loop: return
    except Exception:
        setattr(vc, "loop", False)
    
@bot.slash_command(description="Play a song", guild_ids=[794739329956053063,])
async def play(interaction: Interaction, channel: GuildChannel = SlashOption(channel_types=[ChannelType.voice], description="Voice Channel to Join"), search: str = SlashOption(description="Song Name")):
    search = await wavelink.YouTubeTrack.search(query=search, return_first=True)
    if not interaction.guild.voice_client:
        vc: wavelink.Player = await channel.connect(cls=wavelink.Player)
    elif not getattr(interaction.author.voice, "channel", None):
        return await interaction.send("join a voice channel first lol")
    else:
        vc: wavelink.Player = interaction.guild.voice_client
    
    if vc.queue.is_empty and not vc.is_playing():
        await vc.play(search)
        await interaction.send(f'Playing `{search.title}`')          
    else:
        await vc.queue.put_wait(search)
        await interaction.send(f'Added `{search.title}` to the queue...')
    vc.interaction = interaction
    try:
        if vc.loop: return
    except Exception:
        setattr(vc, "loop", False)
    
@bot.command()
async def pause(ctx: commands.Context):
    if not ctx.voice_client:
        return await ctx.send("im not even in a vc... so how will I pause anything")
    elif not getattr(ctx.author.voice, "channel", None):
        return await ctx.send("join a voice channel first lol")
    else:
        vc: wavelink.Player = ctx.voice_client
    if not vc.is_playing():
        return await ctx.send("first play some music")

    await vc.pause()
    await ctx.send("paused ya music :D")
    
@bot.command()
async def resume(ctx: commands.Context):
    if not ctx.voice_client:
        return await ctx.send("im not even in a vc... so how will I pause anything")
    elif not getattr(ctx.author.voice, "channel", None):
        return await ctx.send("join a voice channel first lol")
    else:
        vc: wavelink.Player = ctx.voice_client
    if vc.is_playing():
        return await ctx.send("music is already playing!")

    await vc.resume()
    await ctx.send("ayye the music is back on!")
    
@bot.command()
async def skip(ctx: commands.Context):
    if not ctx.voice_client:
        return await ctx.send("im not even in a vc... so how will I pause anything")
    elif not getattr(ctx.author.voice, "channel", None):
        return await ctx.send("join a voice channel first lol")
    else:
        vc: wavelink.Player = ctx.voice_client
    if not vc.is_playing():
        return await ctx.send("first play some music")
    
    try:
        next_song = vc.queue.get()
        await vc.play(next_song)
        await ctx.send(content=f"Now Playing `{next_song}`")
    except Exception:
        return await ctx.send("The queue is empty!")
    
    await vc.stop()
    await ctx.send("stopped the song")
    
@bot.command()
async def disconnect(ctx: commands.Context):
    if not ctx.voice_client:
        return await ctx.send("im not even in a vc... so how will I resume anything")
    elif not getattr(ctx.author.voice, "channel", None):
        return await ctx.send("join a voice channel first lol")
    else:
        vc: wavelink.Player = ctx.voice_client
    
    await vc.disconnect()
    await ctx.send("cya laterr")
    
@bot.command()
async def loop(ctx: commands.Context):
    if not ctx.voice_client:
        return await ctx.send("im not even in a vc... so how will I loop anything")
    elif not getattr(ctx.author.voice, "channel", None):
        return await ctx.send("join a voice channel first lol")
    vc: wavelink.Player = ctx.voice_client
    if not vc.is_playing():
        return await ctx.send("first play some music so i can loop it")
    try: 
        vc.loop ^= True
    except:
        setattr(vc, "loop", False)
    if vc.loop:
        return await ctx.send("loooooooooooooooooooooooooooooooooop timeee")
    else:
        return await ctx.send("no more loop time :(")

@bot.command()
async def queue(ctx: commands.Context):
    if not ctx.voice_client:
        return await ctx.send("im not even in a vc...")
    elif not getattr(ctx.author.voice, "channel", None):
        return await ctx.send("join a voice channel first lol")
    vc: wavelink.Player = ctx.voice_client

    if vc.queue.is_empty:
        return await ctx.send("the queue is empty smh")
    
    em = nextcord.Embed(title="Queue")
    
    queue = vc.queue.copy()
    songCount = 0
    for song in queue:
        songCount += 1
        em.add_field(name=f"Song Num {str(songCount)}", value=f"`{song}`")
        
    await ctx.send(embed=em)

@bot.command()
async def volume(ctx: commands.Context, volume: int):
    if not ctx.voice_client:
        return await ctx.send("im not even in a vc... so how will I change the volume on anything")
    elif not getattr(ctx.author.voice, "channel", None):
        return await ctx.send("join a voice channel first lol")
    else:
        vc: wavelink.Player = ctx.voice_client
    if not vc.is_playing():
        return await ctx.send("first play some music")
    
    if volume > 100:
        return await ctx.send('thats wayy to high')
    elif volume < 0:
        return await ctx.send("thats way to low")
    await ctx.send(f"Set the volume to `{volume}%`")
    return await vc.set_volume(volume)

@bot.command()
async def nowplaying(ctx: commands.Context):
    if not ctx.voice_client:
        return await ctx.send("im not even in a vc... so how will I see whats playing")
    elif not getattr(ctx.author.voice, "channel", None):
        return await ctx.send("join a voice channel first lol")
    else:
        vc: wavelink.Player = ctx.voice_client
    
    if not vc.is_playing(): 
        return await ctx.send("nothing is playing")

    em = nextcord.Embed(title=f"Now Playing {vc.track.title}", description=f"Artist: {vc.track.author}")
    em.add_field(name="Duration", value=f"`{str(datetime.timedelta(seconds=vc.track.length))}`")
    em.add_field(name="Extra Info", value=f"Song URL: [Click Me]({str(vc.track.uri)})")
    return await ctx.send(embed=em)

@bot.command()
async def splay(ctx: commands.Context, *, search: str):
    if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
    elif not getattr(ctx.author.voice, "channel", None):
        return await ctx.send("join a voice channel first lol")
    else:
        vc: wavelink.Player = ctx.voice_client
        
    if vc.queue.is_empty and not vc.is_playing():
        try:
            track = await spotify.SpotifyTrack.search(query=search, return_first=True)
            await vc.play(track)
            await ctx.send(f'Playing `{track.title}`')
        except Exception as e:
            await ctx.send("Please enter a spotify **song url**.")
            return print(e)
    else:
        await vc.queue.put_wait(search)
        await ctx.send(f'Added `{search.title}` to the queue...')
    vc.ctx = ctx
    try:
        if vc.loop: return
    except Exception:
        setattr(vc, "loop", False)

bot.run("token")
