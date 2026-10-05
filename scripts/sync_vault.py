#!/usr/bin/env python3
"""Syncs the repo with GitHub, then mirrors it into the Obsidian vault.

All sync logic lives here instead of being duplicated as inline shell
text hand-edited in Shortcuts.app. The vault mirror uses rsync
--update, so a note you edited directly in Obsidian (newer mtime than
the repo's copy) is left alone rather than overwritten -- it just
never flows back into git either.
"""
import os
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

REPO_DIR = Path(__file__).resolve().parent.parent
load_dotenv(REPO_DIR / ".env")

VAULT_DIR = os.environ.get("OBSIDIAN_BASE_DIR")

RSYNC_EXCLUDES = [
    ".git", ".obsidian", "__pycache__", "chroma_db", ".DS_Store", ".env", ".claude",
]


def run(cmd, check=False):
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=REPO_DIR, check=check)


def git_sync():
    run(["git", "add", "-A"])
    run(["git", "commit", "-m", f"pre-sync: {datetime.now()}", "--allow-empty"])
    run(["git", "pull", "--rebase", "origin", "main"], check=True)
    run(["git", "push", "origin", "main"], check=True)


def mirror_to_vault():
    if not VAULT_DIR or not os.path.isdir(VAULT_DIR):
        print(f"OBSIDIAN_BASE_DIR ({VAULT_DIR!r}) not set or missing, skipping vault mirror.")
        return
    cmd = ["rsync", "-avc", "--update"]
    for pattern in RSYNC_EXCLUDES:
        cmd += ["--exclude", pattern]
    cmd += [f"{REPO_DIR}/", f"{VAULT_DIR}/"]
    run(cmd, check=True)


def main():
    git_sync()
    mirror_to_vault()


if __name__ == "__main__":
    main()
