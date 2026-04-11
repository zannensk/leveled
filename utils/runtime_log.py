from datetime import datetime
from pathlib import Path
import traceback

APP_DIR_NAME = ".leveled"
LOG_FILE_NAME = "runtime.log"


def _log_file_path():
    home = Path.home()
    app_dir = home / APP_DIR_NAME
    try:
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir / LOG_FILE_NAME
    except Exception:
        return Path.cwd() / LOG_FILE_NAME


def log(message):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    try:
        print(line)
    except Exception:
        pass
    try:
        log_file = _log_file_path()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def log_exception(context, exc):
    log(f"[ERROR] {context}: {exc}")
    try:
        tb = traceback.format_exc()
        log(tb.rstrip())
    except Exception:
        pass
