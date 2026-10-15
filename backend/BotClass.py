"""
BotClass.py — Bot data class.
"""

from arena.arenaClass import Arena


class Bot:
    def __init__(self, name: str, status: str, kit, agent: str):
        self.name = name
        self.status = status
        self.kit = kit
        self.agent = agent
        self.pair: "Bot" = "NONE"
        self.arena = ""

    def updateBot(self, status: str):
        self.status = status

    def pairAgainst(self, partner: "Bot"):
        self.pair = partner
        partner.pair = self

    def setArena(self, arena: Arena):
        self.arena = arena
