import kits.kitBase as kit
from BotClass import Bot

bots = []

kitSetup = []

def addBot(bot):
    bots.append(bot)

def updateBots():
    # Checks bot statuts
    return 0

def updateBot(name, status):
    # Updates the status of a bot
    bots[name] = status

def printStatus():
    # Prints the status of all bots
    c = 0
    for bot in bots:
        c += 1
        print(c + bot)

def giveBotKit(bot):
    return kit.kitSetup

def pairBot(bot: Bot):
    for b in bots:
        if b.pair == "NONE" and b != bot:
            bot.pairAgainst(b)
            return 1
    return 0
