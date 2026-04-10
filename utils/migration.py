import os
import shutil
from pathlib import Path
from config.settings import USER_DATA_DIR, DB_FILE

def migrate_legacy_data():
    """
    On first run, check if legacy data exists in the project root 
    or in the old ~/.task_overlay dir, and move it to the ~/.leveled directory.
    """
    home = Path.home()
    old_app_dir = home / ".task_overlay"
    current_app_dir = Path(USER_DATA_DIR)
    
    # 1. Rename entire ~/.task_overlay to ~/.leveled if necessary
    if old_app_dir.exists() and not current_app_dir.exists():
        try:
            os.rename(str(old_app_dir), str(current_app_dir))
        except Exception:
            current_app_dir.mkdir(parents=True, exist_ok=True)
    elif not current_app_dir.exists():
        current_app_dir.mkdir(parents=True, exist_ok=True)
        
    # Look for files in the parent directory of this module (project root)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    legacy_db = os.path.join(project_root, "progress.db")
    legacy_history_json = os.path.join(project_root, "history.json")
    legacy_progress_json = os.path.join(project_root, "progress.json")
    
    # 2. Migrate DB from root
    if not os.path.exists(DB_FILE) and os.path.exists(legacy_db):
        try:
            shutil.copy2(legacy_db, DB_FILE)
        except: pass

    # 3. Migrate JSON files
    new_history = os.path.join(USER_DATA_DIR, "history.json")
    if not os.path.exists(new_history) and os.path.exists(legacy_history_json):
        try:
            shutil.copy2(legacy_history_json, new_history)
        except: pass
        
    new_progress = os.path.join(USER_DATA_DIR, "progress.json")
    if not os.path.exists(new_progress) and os.path.exists(legacy_progress_json):
        try:
            shutil.copy2(legacy_progress_json, new_progress)
        except: pass

def apply_pending_imports():
    """
    Checks for .pending files and replaces the live ones.
    This runs at the start of main.py before DB init.
    """
    from config.settings import USER_DATA_DIR
    import os
    
    # 1. First, check if there's a pending DB swap
    pending_db = os.path.join(USER_DATA_DIR, "progress.db.pending")
    if os.path.exists(pending_db):
        print(" >> Detected pending database import. Purging session caches...")
        # Purge SQLite WAL/SHM files to prevent corruption during swap
        for ext in ["-wal", "-shm", ".db-wal", ".db-shm"]:
            f = os.path.join(USER_DATA_DIR, f"progress.db{ext}")
            try:
                if os.path.exists(f): os.remove(f)
            except: pass
            
    # 2. Perform the swap for all files
    for filename in ["progress.db", "history.json", "progress.json"]:
        pending = os.path.join(USER_DATA_DIR, f"{filename}.pending")
        live = os.path.join(USER_DATA_DIR, filename)
        if os.path.exists(pending):
            try:
                if os.path.exists(live):
                    os.remove(live)
                os.rename(pending, live)
                print(f" >> Applied pending import: {filename}")
                
                # If this was the database, force WAL cleanup so Flask doesn't deadlock
                if filename == "progress.db":
                    try:
                        import sqlite3
                        conn = sqlite3.connect(live, timeout=10)
                        # Force checkpoint to flush any pending WAL data
                        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                        # Switch to simpler journal mode so no WAL files are needed
                        conn.execute("PRAGMA journal_mode=DELETE")
                        conn.commit()
                        conn.close()
                        print(" >> Database WAL flushed and journal mode reset to DELETE.")
                    except Exception as db_e:
                        print(f" !! Warning: Could not reset DB journal mode: {db_e}")
                        
            except Exception as e:
                print(f" !! Failed to apply pending {filename}: {e}")

