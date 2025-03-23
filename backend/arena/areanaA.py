from arena.arenaClass import Arena as ac

#Set for worldA in server file
# coords AR1: {[4 17 30], [4 17 46]}
# coords AR1: {[4 17 130], [4 17 146]}
# coords AR1: {[4 17 230], [4 17 246]}
# coords AR4: {[4 17 330], [4 17 346]}
Arenas = []
Arenas.append(ac([[4, 17, 30], [4, 17, 46]], "open", "Arena 1"))
Arenas.append(ac([[4, 17, 130], [4, 17, 146]], "open", "Arena 2"))
Arenas.append(ac([[4, 17, 230], [4, 17, 246]], "open", "Arena 3"))
Arenas.append(ac([[4, 17, 330], [4, 17, 346]], "open", "Arena 4"))