class Arena:
    def __init__(self, spawnCoords: list, status: str, name: str):
        self.spawnCoords = []
        for i in range(len(spawnCoords)):
            self.spawnCoords.append(spawnCoords[i])
        self.status = status
        self.name = name
