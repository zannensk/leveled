import threading
import time
import requests
import sys

def main():
    print(" === Leveled Initialization ===")
    
    # 1. Handle pending imports from previous session (Atomic Swap)
    from utils.migration import apply_pending_imports, migrate_legacy_data
    apply_pending_imports()
    
    # 2. Migrate legacy data
    print("[1/3] Checking data migration...")
    migrate_legacy_data()

    # Delay importing server/overlay until AFTER data is swapped and migrated.
    from services.server import run_server
    from ui.overlay import run_overlay

    
    # 2. Start the Flask background server
    print(f"[2/3] Starting backend server on port 5123...")
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # 3. Wait and verify server status
    print("[3/3] Verifying server health...")
    success = False
    for i in range(10):
        time.sleep(1)
        try:
            r = requests.get("http://127.0.0.1:5123/api/ping", timeout=1, proxies={"http": None, "https": None})
            if r.status_code == 200:
                success = True
                print(" >> Server is UP and healthy.")
                break
        except Exception as e:
            print(f" ... waiting for server... ({type(e).__name__}: {e})")

    
    # 4. Start the UI overlay
    print(" >> Launching Desktop Overlay...")
    run_overlay()
    
    # 5. Keep server alive for Dashboard
    print(" >> Overlay closed. Server remains active for Dashboard. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print(" >> Shutting down...")

if __name__ == "__main__":
    main()
