r"""JSON save/load for game progress and settings -- crash-safe and update-safe.

WHERE SAVES LIVE
----------------
Saves are stored in a stable per-user folder OUTSIDE the game directory:
  Windows : %APPDATA%\HarvestDuo\
  Linux   : ~/.local/share/HarvestDuo/   (or $XDG_DATA_HOME)
This is the important fix: updating or replacing the game folder can no longer
wipe your progress, because the save isn't inside the game folder anymore.
The first time this version runs, any old save sitting next to main.py is
migrated into the new folder automatically (one time only).

FILES
-----
  savegame.json      : full game state
  savegame.bak       : the PREVIOUS good save, kept automatically on every write
  savegame.corrupt   : a copy of a save that failed to load (kept for recovery)
  savegame_error.txt : traceback of the last failed load (for diagnosis)
  settings.json      : audio volumes + fullscreen

Saving is atomic (temp file -> fsync -> os.replace), so a crash mid-write can
never truncate the existing save. Loading falls back to .bak if the main file is
missing or unreadable, so a single bad file never costs you your progress.
"""
import json
import os
import shutil

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _user_dir():
    """A stable folder that survives game-folder updates."""
    base = os.environ.get("APPDATA")                       # Windows
    if not base:
        base = os.environ.get("XDG_DATA_HOME") or \
            os.path.join(os.path.expanduser("~"), ".local", "share")
    d = os.path.join(base, "HarvestDuo")
    try:
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        return _GAME_ROOT                                  # fallback: old behaviour


_DIR = _user_dir()
SAVE_PATH = os.path.join(_DIR, "savegame.json")
BAK_PATH = os.path.join(_DIR, "savegame.bak")
TMP_PATH = os.path.join(_DIR, "savegame.tmp")
CORRUPT_PATH = os.path.join(_DIR, "savegame.corrupt")
ERROR_LOG = os.path.join(_DIR, "savegame_error.txt")
SETTINGS_PATH = os.path.join(_DIR, "settings.json")


def _migrate_once():
    """Move a pre-existing in-folder save into the new location, exactly once."""
    if _DIR == _GAME_ROOT:
        return                                             # nowhere to migrate from
    marker = os.path.join(_DIR, ".migrated")
    if os.path.exists(marker):
        return
    for name, dst in (("savegame.json", SAVE_PATH), ("settings.json", SETTINGS_PATH)):
        old = os.path.join(_GAME_ROOT, name)
        try:
            if os.path.exists(old) and not os.path.exists(dst):
                shutil.copy2(old, dst)
        except Exception:
            pass
    try:
        with open(marker, "w", encoding="utf-8") as f:
            f.write("ok")
    except Exception:
        pass


_migrate_once()


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def has_save():
    return os.path.exists(SAVE_PATH) or os.path.exists(BAK_PATH)


def load_game():
    """Return the best available save: the main file, or the backup if the main
    one is missing/corrupt. Never raises."""
    data = _read(SAVE_PATH)
    if data is not None:
        return data
    return _read(BAK_PATH)


def save_game(data):
    """Atomically persist `data`, keeping the previous good save as .bak.

    Returns True on success. On any failure the existing savegame.json is left
    untouched (we only os.replace() once the new file is fully written)."""
    try:
        with open(TMP_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        if os.path.exists(SAVE_PATH):
            try:
                shutil.copy2(SAVE_PATH, BAK_PATH)
            except Exception:
                pass
        os.replace(TMP_PATH, SAVE_PATH)
        return True
    except Exception:
        try:
            if os.path.exists(TMP_PATH):
                os.remove(TMP_PATH)
        except Exception:
            pass
        return False


def preserve_corrupt():
    """Copy a save that failed to load aside so it isn't lost and can be recovered."""
    try:
        if os.path.exists(SAVE_PATH):
            shutil.copy2(SAVE_PATH, CORRUPT_PATH)
    except Exception:
        pass


def log_error(text):
    """Record why a load failed, to help diagnose without losing the save."""
    try:
        with open(ERROR_LOG, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass


def delete_game():
    """Wipe all save files (only used by 'New Game')."""
    for p in (SAVE_PATH, BAK_PATH, TMP_PATH, CORRUPT_PATH):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


def save_location():
    """Where saves live (for showing the player)."""
    return _DIR


def load_settings():
    return _read(SETTINGS_PATH)


def save_settings(data):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return True
    except Exception:
        return False
