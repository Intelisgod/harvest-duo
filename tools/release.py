"""Developer-only release helper for Harvest Duo (run via the .bat wrappers).

    py tools/release.py setup   one-time: create the public GitHub repo, point
                                updater.py at it, push, build the zip to send
    py tools/release.py push    every update: smoke-test, commit, push
    py tools/release.py zip     rebuild the one-time zip for the other player

Personal files (memories/, anniversary.html) are gitignored and double-checked
here so they can never reach the public repo; they travel only inside the zip.
"""
import os
import re
import shutil
import subprocess
import sys
import zipfile

# Thai messages must never crash on a non-UTF-8 console (would silently skip the update)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REPO_NAME = "harvest-duo"
ZIP_NAME = "HarvestDuo_for_girlfriend.zip"
PRIVATE_PREFIXES = ("memories/", "anniversary.html", "Anniversary-Surprise")

# left out of the zip: dev-only files, local saves, caches, the zip itself
ZIP_SKIP_NAMES = {".git", "__pycache__", ".version", "savegame.json", "savegame.bak",
                  "savegame.tmp", "savegame.corrupt", "savegame_error.txt",
                  "settings.json", ".migrated", "Anniversary-Surprise.zip", ZIP_NAME,
                  "push_update.bat", "setup_github.bat", "SETUP_GITHUB.txt"}
ZIP_SKIP_EXTS = (".pyc", ".mov")                    # .mov: the page uses the .mp4 copies


def run(*cmd, check=True, capture=False):
    r = subprocess.run(cmd, cwd=ROOT, text=True, encoding="utf-8",
                       capture_output=capture)
    if check and r.returncode != 0:
        raise SystemExit(f"\n[!] คำสั่งล้มเหลว: {' '.join(cmd)}\n{(r.stderr or '') if capture else ''}")
    return (r.stdout or "").strip() if capture else r.returncode


def have(tool):
    return shutil.which(tool) is not None


def smoke_test():
    print("\n== ทดสอบเกมก่อนส่ง (smoke test ~15 วิ) ==")
    if run(sys.executable, os.path.join("tools", "smoke_test.py"), check=False) != 0:
        ans = input("\n[!] เทสไม่ผ่าน — ถ้าส่งไป แฟนจะได้เวอร์ชันที่อาจพัง. ส่งต่อไหม? (y/N): ")
        if ans.strip().lower() != "y":
            raise SystemExit("ยกเลิก — ยังไม่ได้ส่งอะไรขึ้นไป")


def stage_and_check():
    run("git", "add", "-A")
    staged = run("git", "diff", "--cached", "--name-only", capture=True).splitlines()
    leaked = [p for p in staged if p.startswith(PRIVATE_PREFIXES)]
    if leaked:
        run("git", "reset", "-q")
        raise SystemExit("[!] เจอไฟล์ส่วนตัวกำลังจะขึ้น repo สาธารณะ — หยุดไว้ก่อน:\n  "
                         + "\n  ".join(leaked))
    return staged


def current_repo():
    src = open(os.path.join(ROOT, "updater.py"), encoding="utf-8").read()
    return re.search(r'^REPO = "([^"]+)"', src, re.M).group(1)


def set_repo(full_name):
    path = os.path.join(ROOT, "updater.py")
    src = open(path, encoding="utf-8").read()
    src = re.sub(r'^REPO = "[^"]*"', f'REPO = "{full_name}"', src, count=1, flags=re.M)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)


def build_zip():
    if "USERNAME/REPO" in current_repo():
        raise SystemExit("[!] ยังไม่ได้ตั้ง repo — รัน setup_github.bat ก่อน ไม่งั้นเครื่องแฟนจะไม่อัปเดต")
    out = os.path.join(ROOT, ZIP_NAME)
    sha = run("git", "rev-parse", "HEAD", capture=True) if os.path.isdir(os.path.join(ROOT, ".git")) else ""
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = [d for d in dirnames if d not in ZIP_SKIP_NAMES
                           and not d.endswith((".new", ".old"))]
            for fn in filenames:
                if fn in ZIP_SKIP_NAMES or fn.lower().endswith(ZIP_SKIP_EXTS):
                    continue
                full = os.path.join(dirpath, fn)
                zf.write(full, os.path.join("HarvestDuo", os.path.relpath(full, ROOT)))
        if sha:                                      # so the first launch doesn't re-download
            zf.writestr("HarvestDuo/.version", sha)
    print(f"\nสร้างไฟล์ส่งแฟนแล้ว: {out}  ({os.path.getsize(out) / 1e6:.0f} MB)")


def setup():
    for tool, url in (("git", "https://git-scm.com/download/win"), ("gh", "https://cli.github.com")):
        if not have(tool):
            raise SystemExit(f"[!] ยังไม่มี {tool} — ติดตั้งจาก {url} แล้วลองใหม่")
    if subprocess.run(["gh", "auth", "status"], capture_output=True).returncode != 0:
        print("\n== ล็อกอิน GitHub (เปิดเบราว์เซอร์ให้กดยืนยันเอง) ==")
        run("gh", "auth", "login", "--hostname", "github.com", "--git-protocol", "https", "--web")
    run("gh", "auth", "setup-git", check=False)
    owner = run("gh", "api", "user", "--jq", ".login", capture=True)
    name = input(f"\nชื่อ repo (Enter = {DEFAULT_REPO_NAME}): ").strip() or DEFAULT_REPO_NAME
    full = f"{owner}/{name}"
    print(f"repo: https://github.com/{full}  (Public — โค้ดเกมเท่านั้น ไม่มีรูป/หน้าครบรอบ)")

    if not os.path.isdir(os.path.join(ROOT, ".git")):
        run("git", "init", "-q", "-b", "main")
    set_repo(full)
    smoke_test()
    stage_and_check()
    if run("git", "diff", "--cached", "--quiet", check=False) != 0:
        run("git", "commit", "-q", "-m", "Harvest Duo: first upload")

    has_origin = run("git", "remote", check=False, capture=True).split().count("origin") > 0
    if not has_origin:
        exists = subprocess.run(["gh", "repo", "view", full], capture_output=True).returncode == 0
        if exists:
            run("git", "remote", "add", "origin", f"https://github.com/{full}.git")
        else:
            run("gh", "repo", "create", full, "--public", "--source", ".", "--remote", "origin")
    run("git", "push", "-u", "origin", "main")
    build_zip()
    print("\nเสร็จ! ส่งไฟล์ zip ข้างบนให้แฟน 'ครั้งเดียว' — ต่อไปกด push_update.bat ได้เลย")


def push():
    if not os.path.isdir(os.path.join(ROOT, ".git")) or "USERNAME/REPO" in current_repo():
        raise SystemExit("[!] ยังไม่ได้ตั้งค่า — รัน setup_github.bat ครั้งแรกก่อน")
    smoke_test()
    staged = stage_and_check()
    if not staged:
        print("\nไม่มีอะไรเปลี่ยน — ไม่ต้องส่ง")
        return
    msg = input(f"\nแก้ {len(staged)} ไฟล์ — พิมพ์สิ่งที่แก้ครั้งนี้ (เว้นว่างได้): ").strip() or "update"
    run("git", "commit", "-q", "-m", msg)
    run("git", "push")
    print("\nส่งขึ้น GitHub แล้ว — แฟนกด \"Play HarvestDuo\" ครั้งต่อไปจะได้เวอร์ชันนี้อัตโนมัติ")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"setup": setup, "push": push, "zip": build_zip}.get(
        cmd, lambda: sys.exit(__doc__))()
