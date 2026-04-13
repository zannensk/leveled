import socket
import threading
import time

import requests

from utils.runtime_log import log, log_exception

SERVER_PORT = 5123
SERVER_BASE = f"http://127.0.0.1:{SERVER_PORT}"
PING_URL = f"{SERVER_BASE}/api/ping"

HTTP = requests.Session()
HTTP.trust_env = False


def is_local_port_open(port, timeout=0.4):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def ping_server(timeout=0.8):
    try:
        resp = HTTP.get(PING_URL, timeout=timeout)
        if resp.status_code != 200:
            return False
        payload = resp.json()
        return payload.get("status") == "pong"
    except Exception:
        return False


def wait_for_server(max_wait_seconds=12):
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        if is_local_port_open(SERVER_PORT) and ping_server(timeout=0.6):
            return True
        time.sleep(0.3)
    return False


def main():
    log("=== Leveled Initialization ===")

    log(f"[1/4] Checking for existing server on port {SERVER_PORT}...")
    server_already_online = is_local_port_open(SERVER_PORT) and ping_server(timeout=0.8)
    server_started_here = False

    if server_already_online:
        log(" >> [REUSE] Existing server is healthy. Reusing it.")
    else:
        log("[2/4] Initializing data...")
        try:
            from utils.migration import apply_pending_imports, migrate_legacy_data

            apply_pending_imports()
            migrate_legacy_data()
        except Exception as exc:
            log_exception("Data initialization failed", exc)

        try:
            from services.server import run_server

            log("[3/4] Starting backend server...")
            server_thread = threading.Thread(target=run_server, daemon=True, name="leveled-server")
            server_thread.start()
            server_started_here = True

            log(" >> Verifying server health...")
            if wait_for_server(max_wait_seconds=12):
                log(" >> Server is UP and healthy.")
            else:
                log(" !! Server did not become healthy within 12 seconds.")
        except Exception as exc:
            log_exception("Failed to start backend server thread", exc)
    if server_already_online:
        log("[2/4] Skipping data migration (using active server).")
        log("[3/4] Background server already active.")

    try:
        from ui.overlay import run_overlay
    except Exception as exc:
        log_exception("Failed to import overlay", exc)
        raise

    log(" >> [4/4] Launching Desktop Overlay...")
    try:
        run_overlay()
    except Exception as exc:
        log_exception("Overlay crashed", exc)
        raise

    if server_started_here:
        log(" >> Overlay closed. Server remains active for Dashboard. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            log(" >> Shutting down...")


if __name__ == "__main__":
    main()
