import urllib.request
import json

base = "http://localhost:8000"

def fetch(endpoint):
    try:
        req = urllib.request.Request(base + endpoint)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"Error fetching {endpoint}: {e}")
        return None

# Stats
stats = fetch("/stats")
if stats:
    print("=== STATS ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

print()

# Reward progression (last 10)
prog = fetch("/reward-progression")
if prog:
    entries = prog.get("progression", [])
    print(f"=== REWARD PROGRESSION ({len(entries)} total intervals) ===")
    for p in entries[-15:]:
        types = p.get("reward_types", {})
        type_summary = {k: round(v.get("amount", v) if isinstance(v, dict) else v, 3) for k, v in types.items()}
        print(f"  Int {p['interval']:>3}: loss={p['loss']:>8.4f}  total_r={p['total_rewards']:>8.2f}  "
              f"avg_r={p['avg_reward']:>7.4f}  samples={p['samples_trained']:>4}  types={type_summary}")

print()

# Game state
gs = fetch("/game-state")
if gs:
    print("=== GAME STATE ===")
    for bot in gs.get("bots", []):
        print(f"  {bot['name']}: status={bot['status']} model={bot.get('model_version','?')} "
              f"tick={bot.get('tick_count',0)} score={bot.get('score', 0):.2f}")
    print(f"  Training: samples={gs['training']['total_samples']} last_loss={gs['training']['last_loss']:.4f}")

print()

# Recent reward events (last few)
events = fetch("/reward-events")
if events:
    print("=== RECENT REWARD EVENTS ===")
    for bot_name, evts in events.get("bots", {}).items():
        print(f"  {bot_name}: {len(evts)} events")
        for e in evts[-5:]:
            ev = e.get("event", {})
            print(f"    {e.get('source','mod')} | {ev.get('type','?')}: amount={ev.get('amount', '?')}")
