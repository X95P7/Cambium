import os
from fastapi import FastAPI, Request
from mcrcon import MCRcon
import asyncio
import multiprocessing
import botController as botController
from BotClass import Bot
from kits import classicKit
from kits.kitBase import Kit
from arena import areanaA

arenas = areanaA.Arenas

app = FastAPI()

RCON_HOST = os.getenv("RCON_HOST", "mc-forge")  # "localhost" if not using Docker
RCON_PORT = int(os.getenv("RCON_PORT", 25575))
RCON_PASSWORD = os.getenv("RCON_PASSWORD", "minecraft")

# Use multiprocessing for running the RCON command in a separate process
def mc_command(command: str):
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = mcr.command(command)
        return response
    except Exception as e:
        return str(e)

# Helper function to run the command in a separate process
def run_rcon_command(command: str):
    with multiprocessing.Pool(1) as pool:
        result = pool.apply(mc_command, (command,))
    return result

async def send_mc_command(command: str):
    loop = asyncio.get_event_loop()
    # Run the RCON command in a separate process
    result = await loop.run_in_executor(None, run_rcon_command, command)
    return {"sent_command": command, "response": result}

@app.post("/send-command/")
async def send_command(command: str):
    return await send_mc_command(command)

@app.post("/bot-setup/")
async def bot_setup(request: Request):
    data = await request.json()
    name = data.get("name")
    print(name)
    currentBot = Bot(name, "ready", Kit(classicKit.kitStart, classicKit.kitEnd, name), "agent")
    botController.addBot(currentBot)
    await giveKit(currentBot)
    move = botController.pairBot(currentBot)
    if move == 1:
        await fightBots(currentBot, currentBot.pair)

    return await send_mc_command(f"/say Bot {name} has been added to the game.")


@app.post("/death/")
async def death(request: Request):
    data = await request.json()
    name = data.get("name")
    bot = getBotByName(name)
    bot.updateBot("dead")
    bot.arena.status = "open"
    fightBots(bot, bot.pair)
    
    return await send_mc_command(f"/say Bot {name} has died!")

async def giveKit(bot: Bot):
    for command in bot.kit.commands:
        await send_mc_command(command)

def getBotByName(name):
    for bot in botController.bots:
        if bot.name == name:
            return bot
    return None

async def fightBots(bot1, bot2):
    arena = getOpenArena()
    if arena == None:
        print("No open arenas")
        return await send_mc_command(f"/say ERROR: No open areans for {bot1.name} and {bot2.name} to fight in.")
    await giveKit(bot1)
    await giveKit(bot2)
    bot1.updateBot("fighting")
    bot2.updateBot("fighting")
    bot1.setArena(arena.name)
    bot2.setArena(arena.name)
    arena.status = "closed"
    print(f"/tp {bot1.name} {arena.spawnCoords[0]}")
    await send_mc_command(f"/tp {bot1.name} {' '.join(map(str, arena.spawnCoords[0]))}")
    await send_mc_command(f"/tp {bot2.name} {' '.join(map(str, arena.spawnCoords[1]))}")

def getOpenArena():
    for arena in arenas:
        if arena.status == "open":
            return arena
    return None