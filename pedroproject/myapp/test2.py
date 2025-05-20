import discord
from discord.ext import commands
from discord.ui import Button, View

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Define your target channel ID here
TARGET_CHANNEL_ID = 1374018261578027129  # Replace with your actual channel ID

class HiByeButtons(View):
    def __init__(self):
        super().__init__(timeout=30)
        
        hi_button = Button(label="Hi", style=discord.ButtonStyle.green, emoji="👋")
        bye_button = Button(label="Bye", style=discord.ButtonStyle.red, emoji="👋")
        
        hi_button.callback = self.hi_callback
        bye_button.callback = self.bye_callback
        
        self.add_item(hi_button)
        self.add_item(bye_button)
    
    async def hi_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"{interaction.user.mention} said Hi back!", ephemeral=True)
        # Also send to target channel
        target_channel = bot.get_channel(TARGET_CHANNEL_ID)
        if target_channel:
            await target_channel.send(f"{interaction.user.mention} said Hi in {interaction.channel.mention}!")
    
    async def bye_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"{interaction.user.mention} said Bye!", ephemeral=True)
        # Also send to target channel
        target_channel = bot.get_channel(TARGET_CHANNEL_ID)
        if target_channel:
            await target_channel.send(f"{interaction.user.mention} said Bye in {interaction.channel.mention}!")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')

@bot.command()
async def hi(ctx):
    """Sends a greeting with buttons and logs to target channel"""
    view = HiByeButtons()
    await ctx.send("Hello! How would you like to respond?", view=view)
    
    # Send to target channel that someone used the command
    target_channel = bot.get_channel(TARGET_CHANNEL_ID)
    if target_channel:
        await target_channel.send(f"{ctx.author.mention} used !hi in {ctx.channel.mention}")

# Use environment variables or a config file for the token
bot.run('')  # Replace with your actual token