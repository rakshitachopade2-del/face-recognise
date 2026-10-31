"""Run the local API, one durable worker and Vite; Ctrl-C stops only these processes."""
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.umask(0o077)
    for port in (8017, 5177):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise SystemExit(f"Port {port} is in use. Stop the existing POC process before starting another.")
    children = []
    try:
        for command, cwd in (([sys.executable, "-m", "server"], ROOT),
                              ([sys.executable, "-m", "server.worker"], ROOT),
                              (["npm", "run", "dev"], ROOT / "web")):
            children.append(subprocess.Popen(command, cwd=cwd, start_new_session=True))
        print("Local operator simulator: http://127.0.0.1:5177 — Ctrl-C to stop", flush=True)
        while True:
            for child in children:
                try:
                    result = child.wait(timeout=.5)
                except subprocess.TimeoutExpired:
                    continue
                raise SystemExit(f"Local service exited ({result}); stopping this POC's other services.")
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)


if __name__ == "__main__":
    main()
