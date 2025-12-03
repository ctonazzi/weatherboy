import os
import discord
import asyncio
import aiohttp
from dotenv import load_dotenv
from discord.ext import commands
from datetime import datetime, timezone

# init program
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
USER = os.getenv('USER') or ""
print(f'USER AGENT: {USER}')
botFirstStart = True
poll_task = None # This is where the poll loop is held.

# Weather locations
locations = {
    "Marion, IL": "37.7308,-88.9277",
    "Murray, KY": "36.6103,-88.3148",
    "Champaign, IL": "40.1163,-88.2435"
}

# THIS is an empty table to hold the last modified information for any given location.
last_modified = {}

# Alert cache
cache = {}

# Warning messages
messages = {
    "Tornado Emergency": "🟪🌪️🟪 TORNADO EMERGENCY for {} 🟪🌪️🟪\n{}\nSEEK SHELTER IMMEDIATELY. THIS IS A DEADLY SITUATION.", # implement soon
    "PDS Tornado Warning": "🟥🌪️🟥 PDS TORNADO WARNING for {} 🟥🌪️🟥\n{}\nTHIS IS A PARTICULARLY DANGEROUS SITUATION. SEEK SHELTER IMMEDIATELY.", #implement soon
    "Tornado Warning": "🟥🌪️🟥 TORNADO WARNING for {} 🟥🌪️🟥\n{} ({})",
    "Tornado Watch": "🟨🌪️🟨 TORNADO WATCH for {} 🟨🌪️🟨\n{} ({})",
    "Extreme Heat Warning": "🟨🔥🟨 EXTREME HEAT WARNING for {} 🟨🔥🟨\n{} ({})",
    "Extreme Wind Warning": "🟪💨🟪 EXTREME WIND WARNING for {} 🟪💨🟪\n{} ({})\nSUSTAINED WINDS OF 110+ MPH ARE EXPECTED. SEEK SHELTER IMMEDIATELY.",
    "Extreme Cold Warning": "🟨🥶🟨 EXTREME COLD WARNING for {} 🟨🥶🟨\n {} ({})",
    "Destructive Severe Thunderstorm Warning": "🟪⛈️🟪 DESTRUCTIVE SEVERE THUNDERSTORM WARNING for {} 🟪⛈️🟪\n{} ({})",
    "Severe Thunderstorm Warning": "🟥⛈️🟥 SEVERE THUNDERSTORM WARNING for {} 🟥⛈️🟥\n{} ({})",
    "Severe Thunderstorm Watch": "🟨⛈️🟨 SEVERE THUNDERSTORM WATCH for {} 🟨⛈️🟨\n{} ({})",
    "Winter Storm Warning": "🟥🌨️🟥 WINTER STORM WARNING for {} 🟥🌨️🟥\n{} ({})",
    "Winter Storm Watch": "🟨🌨️🟨 WINTER STORM WATCH for {} 🟨🌨️🟨\n{} ({})",
    "Flash Flood Warning": "🟥🌊🟥 FLASH FLOOD WARNING for {} 🟥🌊🟥\n{} ({})",
    "Flood Warning": "🟥🌊🟥 FLOOD WARNING for {} 🟥🌊🟥\n{} ({})",
    "Flood Watch": "🟨🌊🟨 FLOOD WATCH for {} 🟨🌊🟨\n{} ({})",
    "Air Quality Alert": "🟨🌁🟨 AIR QUALITY ALERT for {} 🟨🌁🟨\n{} ({})",
    "Dense Fog Advisory": "🟨🌫️🟨 DENSE FOG ADVISORY for {} 🟨🌫️🟨\n{} ({})",
    "Special Weather Statement": "🟨📣🟨 SPECIAL WEATHER STATEMENT for {} 🟨📣🟨 ({})"
}

# Discord API vars
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

bot = commands.Bot(intents=intents, command_prefix='!')


@bot.event
async def on_ready():
    global botFirstStart
    print(f'{bot.user} successfully connected.')

    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        if botFirstStart:
            asyncio.create_task(msg_loop())
            asyncio.create_task(poll_locations())
            # await channel.send('Weatherboy has been updated.\nUse \'!info\' to learn more.')
            botFirstStart = False
    else:
        print('!!! WEATHERBOY DID NOT FIND THE CHANNEL !!!')

# COMMANDS

@bot.command() # make sure bot is alive
async def ping(ctx):
    await ctx.send("pong")

@bot.command() # view bot info
async def info(ctx):
    with open('info.txt', 'r') as file:
        info = file.read()
    await ctx.send(info)

@bot.command() # emergency quit remotely
async def forcequit(ctx):
    quit()

@bot.command() # view changelog
async def changelog(ctx):
    with open('changelog.txt', 'r') as file:
        info = file.read()
    await ctx.send(info)

@bot.command() # show all active alerts
async def alerts(ctx):
    try:
        alerts = ""
        for alert, tuple in cache.items():
            if tuple[0] == "Tornado Warning":
                alerts += tornadoCheck(f"{tuple[1]}", f"{tuple[3]}", f"{tuple[2]}", f"{tuple[4]}") # name, description, headline, messageType
                alerts += "\n"
            else: 
                alerts += messages[tuple[5]].format(tuple[1], tuple[2], tuple[4])
                alerts += "\n"
        if alerts == "":
            alerts = "No active alerts"
        await bot.get_channel(CHANNEL_ID).send(alerts)
    except Exception as e:
        print(f"Command exception: {e}")

async def fetchAlerts(session, name, point): # Fetches the alerts from NWS API
    try:
        api = f'https://api.weather.gov/alerts/active?point={point}'
        headers = {
            "Accept": "application/ld+json",
            "User-Agent": f"weatherboy_test_bot_automated_alerts, {USER}" # User-Agent required by NWS API.
        }

        if name in last_modified and last_modified[name] is not None:
            headers["If-Modified-Since"] = last_modified[name]

        async with session.get(api, headers=headers) as response:
            if response.status == 200: # GOOD response
                last_modified[name] = response.headers.get("Last-Modified")
                post_data = await response.json() # This actually converts data into JSON
                graph = post_data.get("@graph", []) # convert the alerts into a list.

                if graph == []:
                    print(f"No alerts {getTime()}")
                
                for i in graph:
                    id = i.get("id")
                    event = i.get("event")
                    headline = i.get("headline")
                    description = i.get("description")
                    expires = i.get("expires")
                    messageType = i.get("messageType")
                    tags = i.get("tags", [])
                    if id not in cache and event in messages: # check if in cache AND if the alert type is in the system.
                        await sendAlert(event, name, headline, description, messageType, tags)
                        cache[f"{id}"] = (expires, name, headline, description, messageType, event, tags)
                        print(f"ALERT SENT! {getTime()}")
                        

            elif response.status == 304: # GOOD response, but NO UPDATE.
                print(f'No updates {getTime()}')
            elif response.status == 301: # API ERROR
                post_data = response.json()

                print(f'{post_data.get("title")}\n{post_data.get("status")}\n{post_data.get("detail")}')
            elif response.status == 429: # RATE LIMITED
                print(f'rate limited: error code {response.status} {getTime()}')
                exit() # STOP execution if we get rate limited. This is REALLY bad.
            else:
                print(f'API Error: {response.status}')

    except aiohttp.ClientError as e:
        print(f'Error requesting data: {e}')

async def sendAlert(type, name, headline, description, messageType, tags):
    print(type)
    try:
        # IF statement for the exceptions (tornado, special weather). These need different formatting.
        if type == "Tornado Warning":
            tornadoType = tornadoCheck(name, description, headline, messageType)
            print(tornadoType)
            await bot.get_channel(CHANNEL_ID).send(tornadoType)
        elif type == "Special Weather Statement":
            alert = messages[type].format(name, messageType)
            embedDescription = discord.Embed(title="Special Weather Statement", description=description) # Creates an embedded text box. This looks cool, consider refactoring to support this for ALL alerts.
            await bot.get_channel(CHANNEL_ID).send(f'{alert}\n', embed=embedDescription)
        elif type == "Severe Thunderstorm Warning":
            severeTStorm = severeTCheck(name, headline, messageType, tags)
            await bot.get_channel(CHANNEL_ID).send(severeTStorm)
        else:
            alert = messages[type].format(name, headline, messageType)
            print(alert)
            await bot.get_channel(CHANNEL_ID).send(alert)
    except Exception as e:
        print(f'Exception: {e}. This is likely not in the library of warnings, so either add it or ignore this.')

async def poll_locations():
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    for name, point in locations.items():
                        await fetchAlerts(session, name, point)
                        await asyncio.sleep(6)
                    await clear_cache() # clean it
                    await update_activity() # update it
                    await asyncio.sleep(10)
        except Exception as e:
            print(f'Session exception: {e}. Attempting to create new session.')

# clean cache
async def clear_cache():
    currentTime = datetime.now(timezone.utc)
    todelete = {}
    try:
        for alert, tuple in cache.items():
            expireTime = datetime.fromisoformat(tuple[0])
            if currentTime > expireTime:
                todelete[f'{alert}'] = tuple
                print(f'Marked alert ID {alert} for deletion.')
        for alert in todelete:
            if alert in cache:
                deleted = cache.pop(alert, None)
                print(f'Deleted id: {deleted}') # Debugging line, just to make sure things are being popped properly. Might help if this function explodes again.
                print(f'Alert ID {alert} removed from cache.')
    except Exception as e:
        print(f"Exception in clear_cache: {e}")

async def msg_loop():
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)

    while True:
        msg = await asyncio.to_thread(input)

        if channel:
            try:
                await channel.send(msg)
            except Exception as e:
                print(f"msg_loop Exception: {e}")
        else:
            print("No channel")

async def update_activity():
    try:
        alertCount = len(cache)
        if alertCount == 1:
            await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{alertCount} active alert"))
        else:
            await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{alertCount} active alerts"))
    except Exception as e:
        print(f'Exception in update_activity: {e}')

# non-asyncronous functions
# ------------------------------------------------------------------------------------------------------------------------------------------

# get current time
def getTime():
    return datetime.now().strftime("%H:%M:%S")

# checks if the tornado warning is regular, PDS, or emergency.
def tornadoCheck(name, description, headline, messageType):
    print('TORNADO WARNING, LET US DETERMINE WHAT KIND...')
    description = description.lower()
    headline = headline.lower()
    if "tornado emergency" in headline or "tornado emergency" in description:
        print('TORNADO EMERGENCY')
        alert = messages["Tornado Emergency"].format(name, headline)
        return alert
    elif "particularly dangerous situation" in headline or "particularly dangerous situation" in description:
        print('PDS TORNADO WARNING')
        alert = messages["PDS Tornado Warning"].format(name, headline)
        return alert
    else:
        print('just a regular tornado warning')
        alert = messages["Tornado Warning"].format(name, headline, messageType)
        return alert
    
# checks if severe t-storm is tagged as 'destructive'
def severeTCheck(name, headline, messageType, tags):
    if "DamageThreatDestructive" in tags:
        print("Destructive T-storm")
        alert = messages["Destructive Severe Thunderstorm Warning"].format(name, headline, messageType)
        return alert
    else:
        alert = messages["Severe Thunderstorm Warning"].format(name, headline, messageType)
        return alert

# keep at end
bot.run(TOKEN)
