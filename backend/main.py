import os
from fastapi import FastAPI
from mcrcon import MCRcon
import asyncio
import multiprocessing

app = FastAPI()

RCON_HOST = os.getenv("RCON_HOST", "mc-forge")  # "localhost" if not using Docker
RCON_PORT = int(os.getenv("RCON_PORT", 25575))
RCON_PASSWORD = os.getenv("RCON_PASSWORD", "minecraft")

# Use multiprocessing for running the RCON command in a separate process
def send_mc_command(command: str):
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = mcr.command(command)
        return response
    except Exception as e:
        return str(e)

# Helper function to run the command in a separate process
def run_rcon_command(command: str):
    with multiprocessing.Pool(1) as pool:
        result = pool.apply(send_mc_command, (command,))
    return result

@app.post("/send-command/")
async def send_command(command: str):
    loop = asyncio.get_event_loop()
    # Run the RCON command in a separate process
    result = await loop.run_in_executor(None, run_rcon_command, command)
    return {"sent_command": command, "response": result}
