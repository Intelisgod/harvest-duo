"""Auto-updater for Harvest Duo.

Run automatically by "Play HarvestDuo.bat" before the game starts. Asks GitHub
for the latest commit; only if it differs from the local copy does it download
the repo zip and copy it over the local files. Saves are NOT touched (they live
in %APPDATA%\\HarvestDuo), and neither are the personal files (memories/,
anniversary.html) which are never in the public repo. If there's no internet or
anything goes wrong, it keeps the version already on disk so the game always
still launches.

ONE-TIME SETUP (host/developer): run setup_github.bat - it fills in REPO below.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

# Thai messages must never crash on a non-UTF-8 console (would silently skip the update)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# vvv  filled in by setup_github.bat  (owner/name of the public GitHub repo)  vvv
REPO = "Intelisgod/harvest-duo"
BRANCH = "main"
# ^^^

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(HERE, ".version")

# never overwrite these: git internals, local saves/settings, the personal gift
# files, and .bat files (the running launcher can't be replaced mid-run)
SKIP = {".git", ".gitignore", ".version", "savegame.json", "savegame.bak",
        "savegame.corrupt", "settings.json", "memories", "anniversary.html",
        "Anniversary-Surprise.zip", "__pycache__"}


def _log(msg):
    print("  [auto-update] " + msg)


def _get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": "HarvestDuo"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def _latest_sha():
    data = _get(f"https://api.github.com/repos/{REPO}/commits/{BRANCH}", 10)
    return json.loads(data)["sha"]


def _local_sha():
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _replace_dir(src, dst):
    """Copy src next to dst first, then swap, so a failure never leaves dst half-written."""
    new, old = dst + ".new", dst + ".old"
    shutil.rmtree(new, ignore_errors=True)
    shutil.rmtree(old, ignore_errors=True)
    shutil.copytree(src, new, ignore=shutil.ignore_patterns("__pycache__"))
    if os.path.exists(dst):
        os.rename(dst, old)
    os.rename(new, dst)
    shutil.rmtree(old, ignore_errors=True)


def main():
    if "USERNAME/REPO" in REPO:
        _log("repo ยังไม่ถูกตั้งค่า — ข้ามอัปเดต (เล่นเวอร์ชันในเครื่อง)")
        return
    if os.path.exists(os.path.join(HERE, ".git")):
        # the developer's own checkout: never overwrite work-in-progress with the
        # GitHub copy (it would wipe uncommitted/new files). Players install from
        # the zip, which has no .git, so they still auto-update.
        _log("โฟลเดอร์นักพัฒนา (มี .git) — ข้ามอัปเดตอัตโนมัติ")
        return
    try:
        _log("กำลังตรวจเวอร์ชันล่าสุด...")
        try:
            sha = _latest_sha()
        except Exception:
            sha = ""                                  # API hiccup/rate limit: fall back to always downloading
        if sha and sha == _local_sha():
            _log("เป็นเวอร์ชันล่าสุดอยู่แล้ว")
            return
        data = _get(f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip", 60)
        zf = zipfile.ZipFile(io.BytesIO(data))
        tmp = tempfile.mkdtemp(prefix="hd_update_")
        try:
            zf.extractall(tmp)
            roots = [d for d in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, d))]
            src_root = os.path.join(tmp, roots[0])    # GitHub zips nest under repo-main/
            if not os.path.isdir(os.path.join(src_root, "src")):
                _log("ไฟล์อัปเดตไม่สมบูรณ์ — ข้าม")
                return
            n = 0
            for name in os.listdir(src_root):
                if name in SKIP or name.lower().endswith(".bat"):
                    continue
                s = os.path.join(src_root, name)
                d = os.path.join(HERE, name)
                if os.path.isdir(s):
                    _replace_dir(s, d)
                else:
                    shutil.copy2(s, d)
                n += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if sha:
            with open(VERSION_FILE, "w", encoding="utf-8") as f:
                f.write(sha)
        _log(f"อัปเดตเป็นเวอร์ชันล่าสุดแล้ว ({n} รายการ)")
    except Exception as e:
        _log(f"อัปเดตไม่ได้ (ออฟไลน์?) — เล่นเวอร์ชันในเครื่องต่อได้เลย [{e}]")


if __name__ == "__main__":
    main()
