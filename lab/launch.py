"""Open BoundaryLab without interrupting another local application."""
from __future__ import annotations

import argparse
import json
import socket
import threading
import time
import urllib.request
import webbrowser

PORTS = (8765, *range(8876, 8887))
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def is_boundarylab(port: int) -> bool:
    try:
        base = f"http://127.0.0.1:{port}"
        with HTTP.open(base + "/api/health", timeout=0.4) as response:
            health = json.load(response)
        if not isinstance(health, dict) or not {"simulator_ready", "api_configured", "model_disclosure"} <= health.keys():
            return False
        with HTTP.open(base + "/", timeout=0.4) as response:
            return "BoundaryLab" in response.read(2048).decode("utf-8", errors="replace")
    except (OSError, ValueError, TypeError):
        return False


def select_port() -> tuple[int, bool]:
    for port in PORTS:
        if is_boundarylab(port):
            return port, True
    for port in PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
            candidate.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                candidate.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port, False
    raise RuntimeError("No available local port. Please close an unused local service and try again.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the BoundaryLab workbench")
    parser.add_argument("--check", action="store_true", help="Print selected URL without opening or starting a server")
    args = parser.parse_args()
    port, running = select_port()
    url = f"http://127.0.0.1:{port}/"
    print(f"[BoundaryLab] {'Existing service' if running else 'Starting service'}: {url}", flush=True)
    if args.check:
        return
    if running:
        webbrowser.open(url)
        return

    def open_ready() -> None:
        for _ in range(100):
            if is_boundarylab(port):
                webbrowser.open(url)
                return
            time.sleep(0.1)

    threading.Thread(target=open_ready, daemon=True).start()
    import uvicorn
    uvicorn.run("lab.server:app", host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
