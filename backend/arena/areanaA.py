from arena.arenaClass import Arena as ac

#Set for worldA in server file
# coords AR1: {[4 17 30], [4 17 46]}
# coords AR1: {[4 17 130], [4 17 146]}
# coords AR1: {[4 17 230], [4 17 246]}
# coords AR4: {[4 17 330], [4 17 346]}
Arenas = []
Arenas.append(ac([[-19, 14, 25], [-19, 14, 21]], "open", "Arena 1 s"))
Arenas.append(ac([[-36, 14, 25], [-36, 14, 21]], "open", "Arena 2 s"))
Arenas.append(ac([[-19, 14, 37], [-19, 14, 41]], "open", "Arena 3 s"))
Arenas.append(ac([[-36, 14, 37], [-36, 14, 41]], "open", "Arena 4 s"))
# Arenas.append(ac([[4, 17, 30], [4, 17, 46]], "open", "Arena 3"))
# Arenas.append(ac([[4, 17, 130], [4, 17, 146]], "open", "Arena 4"))
# Arenas.append(ac([[4, 17, 230], [4, 17, 246]], "open", "Arena 5"))
# Arenas.append(ac([[4, 17, 330], [4, 17, 346]], "open", "Arena 6"))