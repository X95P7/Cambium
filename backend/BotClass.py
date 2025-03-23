from arena.arenaClass import Arena

class Bot: 
    def __init__(self, name, status, kit, agent):
        self.name = name
        self.status = status
        self.kit = kit
        self.agent = agent
        self.pair: Bot = "NONE"
        self.arena = ""

    def updateBot(self, status):
        self.status = status

    def printStatus(self):
        print(self.name + self.status)
    
    def clear():
        return "/clear name"
        
    #This should be able to take multiple pairs soon
    def pairAgainst(self, partner):
        self.pair = partner
        partner.pair = self

    def setArena(self, arena: Arena):
        self.arena = arena
