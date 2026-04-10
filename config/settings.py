import os
import sys
from pathlib import Path

# Base App Info
APP_NAME = "Leveled"
SERVER_PORT = 5123
SERVER_BASE = f"http://127.0.0.1:{SERVER_PORT}"
REFRESH_MS = 2000
DIMENSIONS = ["Math", "Algorithm", "Coding", "Project", "Language"]

# Determine if we are running in PyInstaller bundled mode
def get_base_path():
    if getattr(sys, 'frozen', False):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = get_base_path()

# Determine User Data Path (for DB and settings)
def get_user_data_path():
    # Use standard home directory for app data to avoid committing personal info
    home = Path.home()
    app_dir = home / f".{APP_NAME.lower()}"
    app_dir.mkdir(parents=True, exist_ok=True)
    return str(app_dir)

USER_DATA_DIR = get_user_data_path()

# Database File Path
DB_FILE = os.path.join(USER_DATA_DIR, "progress.db")

# Assets
DASHBOARD_HTML_PATH = os.path.join(BASE_DIR, "ui", "dashboard.html")
