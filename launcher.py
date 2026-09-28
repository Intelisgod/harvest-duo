"""
Harvest Duo launcher — makes sure pygame-ce is installed, then starts the game.
Run by "Play HarvestDuo.bat" (after updater.py), or:  py launcher.py
This file auto-updates, so dependency changes go here, not in the .bat.
"""
import os
import subprocess
import sys

# Thai messages must never crash on a non-UTF-8 console (would silently skip the update)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _pip(*args):
    return subprocess.call([sys.executable, "-m", "pip", *args,
                            "--quiet", "--disable-pip-version-check"])


def ensure_pygame_ce():
    """The game is built on pygame-ce. Plain `pygame` shares the same import
    name but behaves differently, so swap it out if that's what's installed."""
    try:
        import pygame
        if getattr(pygame, "IS_CE", False):
            return True
        print("  พบ pygame รุ่นเก่า — เปลี่ยนเป็น pygame-ce...")
        _pip("uninstall", "-y", "pygame")
    except ImportError:
        print("  กำลังติดตั้ง pygame-ce (ครั้งแรกครั้งเดียว)...")
    if _pip("install", "--upgrade", "pygame-ce") != 0:
        print("\n[!] ติดตั้ง pygame-ce ไม่สำเร็จ — เช็กอินเทอร์เน็ตแล้วลองใหม่")
        return False
    return True


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if not ensure_pygame_ce():
        input("\nกด Enter เพื่อปิด...")
        sys.exit(1)
    from src.game import Game
    Game().run()


if __name__ == "__main__":
    main()
