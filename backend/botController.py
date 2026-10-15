"""
botController.py — Bot list management and pairing logic.
"""

from BotClass import Bot

bots = []


def addBot(bot: Bot):
    bots.append(bot)


def pairBot(bot: Bot) -> int:
    """Find an unpaired ready bot and pair it with the given bot.
    Returns 1 if paired, 0 if no partner available."""
    if bot.pair != "NONE":
        return 0
    for b in bots:
        if b.pair == "NONE" and b != bot and b.status == "ready":
            bot.pairAgainst(b)
            return 1
    return 0
