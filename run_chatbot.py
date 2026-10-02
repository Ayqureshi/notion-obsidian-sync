#!/usr/bin/env python3
"""One-command launcher: starts the RAG backend, waits for it to be ready,
then opens the popup UI. Closing the popup stops the backend too."""
import atexit
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO_DIR = Path(__file__).resolve().parent
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
STARTUP_TIMEOUT_SECONDS = 180

load_dotenv(REPO_DIR / ".env")


def is_backend_up():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((BACKEND_HOST, BACKEND_PORT)) == 0


def wait_for_backend(process):
    print("Waiting for chatbot backend to finish indexing...")
    start = time.time()
    while time.time() - start < STARTUP_TIMEOUT_SECONDS:
        if is_backend_up():
            print("Backend ready.")
            return True
        if process.poll() is not None:
            print("Backend process exited unexpectedly - check the output above.")
            return False
        time.sleep(1)
    print(f"Backend did not start within {STARTUP_TIMEOUT_SECONDS}s.")
    return False


def choose_index_folders():
    """Ask which top-level vault folders to index. Empty/Enter = everything."""
    vault_dir = os.environ.get("OBSIDIAN_BASE_DIR")
    if not vault_dir or not os.path.isdir(vault_dir):
        print("OBSIDIAN_BASE_DIR not set or missing, will index the whole vault.")
        return ""

    skip = {"scripts", ".git", ".obsidian", ".github", ".vscode", ".claude"}
    candidates = sorted(
        p.name for p in Path(vault_dir).iterdir()
        if p.is_dir() and p.name not in skip and not p.name.startswith(".")
    )
    if not candidates:
        return ""

    print("\nWhich notes should the chatbot index?")
    for i, name in enumerate(candidates, 1):
        print(f"  {i}. {name}")
    raw = input("Enter numbers separated by commas, or press Enter for everything: ").strip()
    if not raw:
        return ""

    try:
        picked = {int(x) for x in raw.split(",")}
    except ValueError:
        print("Could not parse that, indexing everything instead.")
        return ""

    chosen = [candidates[i - 1] for i in sorted(picked) if 1 <= i <= len(candidates)]
    return ",".join(chosen)


def main():
    backend_process = None
    if is_backend_up():
        print("Backend already running on port 8000, reusing it.")
    else:
        env = os.environ.copy()
        env["CHATBOT_INDEX_FOLDERS"] = choose_index_folders()
        backend_process = subprocess.Popen([sys.executable, "scripts/chatbot.py"], cwd=REPO_DIR, env=env)

        def cleanup():
            if backend_process.poll() is None:
                print("Stopping chatbot backend...")
                backend_process.terminate()
                try:
                    backend_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    backend_process.kill()

        atexit.register(cleanup)

        if not wait_for_backend(backend_process):
            sys.exit(1)

    print("Launching chatbot popup...")
    subprocess.run([sys.executable, "scripts/chatbot_ui.py"], cwd=REPO_DIR)


if __name__ == "__main__":
    main()
