#!/usr/bin/env python3
"""One-command launcher: starts the RAG backend, waits for it to be ready,
then opens the popup UI. Closing the popup stops the backend too."""
import atexit
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
STARTUP_TIMEOUT_SECONDS = 120


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


def main():
    backend_process = None
    if is_backend_up():
        print("Backend already running on port 8000, reusing it.")
    else:
        backend_process = subprocess.Popen([sys.executable, "scripts/chatbot.py"], cwd=REPO_DIR)

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
