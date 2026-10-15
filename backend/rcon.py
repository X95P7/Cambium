"""
rcon.py — RCON communication with the Minecraft server.
Persistent connection with retry logic, thread-safe via lock + single-worker pool.
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from mcrcon import MCRcon, MCRconException
import state

# ═══════════════════════ MCRcon Monkey-patch ═════════════════════════
# Replace signal.alarm (main-thread only) with socket.settimeout.
_MCRcon_orig_connect = MCRcon.connect

def _mcrcon_init(self, host, password, port=25575, tlsmode=0, timeout=5):
    self.host = host
    self.password = password
    self.port = port
    self.tlsmode = tlsmode
    self.timeout = timeout

def _mcrcon_connect(self):
    _MCRcon_orig_connect(self)
    if self.socket and self.timeout:
        self.socket.settimeout(self.timeout)

def _mcrcon_read(self, length):
    data = b""
    while len(data) < length:
        chunk = self.socket.recv(length - len(data))
        if not chunk:
            raise MCRconException("Connection closed by server")
        data += chunk
    return data

MCRcon.__init__ = _mcrcon_init
MCRcon.connect  = _mcrcon_connect
MCRcon._read    = _mcrcon_read

# ═══════════════════════ Connection Management ══════════════════════

_rcon_lock = threading.Lock()
_rcon_conn: MCRcon | None = None
_rcon_pool = ThreadPoolExecutor(max_workers=1)
_gamerules_set = False
_RCON_SPACING_SEC = 0.02


def _get_rcon() -> MCRcon:
    global _rcon_conn
    if _rcon_conn is None:
        _rcon_conn = MCRcon(state.RCON_HOST, state.RCON_PASSWORD, port=state.RCON_PORT)
        _rcon_conn.connect()
    return _rcon_conn


def close():
    """Disconnect the persistent RCON connection."""
    global _rcon_conn
    if _rcon_conn is not None:
        try:
            _rcon_conn.disconnect()
        except Exception:
            pass
        _rcon_conn = None


def mc_command(command: str) -> str:
    """Send a command via RCON with up to 3 retries."""
    with _rcon_lock:
        for attempt in range(3):
            try:
                return _get_rcon().command(command)
            except Exception as e:
                print(f"[RCON ERROR] attempt {attempt+1}/3 '{command}': {e}")
                close()
                if attempt == 2:
                    return f"RCON_FAIL: {e}"
                time.sleep(0.1 * (attempt + 1))
    return "RCON_FAIL: exhausted retries"


async def send(command: str):
    """Async wrapper — runs mc_command in a thread pool."""
    global _gamerules_set
    loop = asyncio.get_event_loop()
    if not _gamerules_set:
        _gamerules_set = True
        await loop.run_in_executor(_rcon_pool, mc_command,
                                   "/gamerule sendCommandFeedback false")
        await loop.run_in_executor(_rcon_pool, mc_command,
                                   "/gamerule commandBlockOutput false")
        await loop.run_in_executor(_rcon_pool, mc_command,
                                   "/gamerule logAdminCommands false")

    await asyncio.sleep(_RCON_SPACING_SEC)
    result = await loop.run_in_executor(_rcon_pool, mc_command, command)
    return {"sent_command": command, "response": result}
