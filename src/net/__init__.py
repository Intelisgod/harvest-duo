"""LAN multiplayer for Harvest Duo.

Authoritative-host model: the host machine runs the real ``Game`` simulation and
plays Player 1; the client machine is a thin renderer that sends its input to the
host and draws the snapshots it receives back, with its own camera locked to
Player 2. This keeps a single source of truth (no desync) — ideal for two
players on the same Wi-Fi / LAN.

Modules:
  protocol  -- length-prefixed JSON framing (pack / Reader)
  transport -- threaded, non-blocking TCP Host and Client

The game-side glue lives in ``src/systems/net_system.py`` (NetMixin).
"""
from .transport import Host, Client, PORT

__all__ = ["Host", "Client", "PORT"]
