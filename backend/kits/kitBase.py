class Kit:
    def __init__(self, kitStart, kitEnd, name):
        self.commands = []
        for i in range(len(kitStart)):
            self.commands.append(kitStart[i] + name + kitEnd[i])
