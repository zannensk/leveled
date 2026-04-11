import flask
from flask import request, jsonify
from flask_cors import CORS
from storage import database
from config.settings import SERVER_PORT, DASHBOARD_HTML_PATH, SERVER_IDLE_SHUTDOWN_SECONDS
from datetime import datetime
import threading
import os
import time
import signal
from werkzeug.serving import make_server

from utils.runtime_log import log, log_exception

app = flask.Flask(__name__)
CORS(app)

# Heartbeat state for auto-shutdown
LAST_HEARTBEAT = time.time()
HEARTBEAT_TIMEOUT = SERVER_IDLE_SHUTDOWN_SECONDS

@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    global LAST_HEARTBEAT
    LAST_HEARTBEAT = time.time()
    return jsonify({"status": "ok"}), 200

@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"status": "pong"}), 200


@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    # Schedule shutdown to allow response to be sent
    import threading
    def kill_soon():
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGINT)
    
    threading.Thread(target=kill_soon).start()
    return jsonify({"status": "shutting down"}), 200





# Initialize DB on start (performs migration if needed)
try:
    database.init_db()
except Exception as exc:
    log_exception("Database initialization failed", exc)

# Transient state for "Active Now" indicator
LAST_ACTIVE = {"keyword": None, "ts": 0}

@app.route("/update", methods=["POST"])
def update_progress():
    req_data = request.json
    # "site" from extension acts as "keyword"
    keyword = req_data.get("site") 
    seconds = req_data.get("active_seconds", 0)

    if not keyword:
        return jsonify({"status": "ignored", "reason": "no site"}), 200

    # Update Active State
    LAST_ACTIVE["keyword"] = keyword
    LAST_ACTIVE["ts"] = datetime.now().timestamp()

    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Update DB
    new_total = database.update_task_progress(today_str, keyword, seconds)
    
    # Return new total (simple feedback)
    return jsonify({"status": "ok", "new_total": new_total}), 200

@app.route("/progress", methods=["GET"])
def get_progress():
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Returns list: [{id, name, goal_min, seconds, keyword}, ...]
    tasks = database.get_daily_progress(today_str)
    
    # Inject Active Status
    now_ts = datetime.now().timestamp()
    for t in tasks:
        # standardizing keyword match
        if t['keyword'] == LAST_ACTIVE['keyword'] and (now_ts - LAST_ACTIVE['ts']) < 90:
            t['active'] = True
        else:
            t['active'] = False
            
    return jsonify(tasks)

@app.route("/tasks", methods=["GET"])
def get_tasks():
    return jsonify(database.get_tasks())

@app.route("/dimensions", methods=["GET"])
def get_dimensions():
    return jsonify(database.get_all_dimensions())

@app.route("/tasks", methods=["POST"])
def add_task():
    data = request.json
    name = data.get("name")
    keyword = data.get("keyword")
    goal = int(data.get("goal", 15))
    dimension = data.get("dimension", "Language")
    
    if not name or not keyword:
        return jsonify({"error": "Missing fields"}), 400
        
    database.add_task(name, keyword, goal, dimension)
    return jsonify({"status": "created"}), 201

@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    database.delete_task(task_id)
    return jsonify({"status": "deleted"}), 200

@app.route("/dimensions/<path:dim_name>", methods=["DELETE"])
def delete_dimension(dim_name):
    try:
        force = request.args.get("force", "0") == "1"
        success = database.delete_dimension(dim_name, force=force)
        if success:
            return jsonify({"status": "deleted"}), 200
        else:
            return jsonify({"error": "Cannot delete dimension with active tasks unless forced"}), 400
    except Exception as e:
        print(f"Delete Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/config", methods=["GET"])
def get_config():
    # Helper for extension to know what to track
    # Returns {keyword: id} or list?
    # Extension needs simple list of keywords typically, or map.
    tasks = database.get_tasks()
    return jsonify({t['keyword']: t['id'] for t in tasks})

@app.route("/history", methods=["GET"])
def history():
    return jsonify(database.get_history())
    
@app.route("/ability_state", methods=["GET"])
def ability_state():
    return jsonify(database.get_ability_state())

@app.route("/calendar", methods=["GET"])
def calendar_data():
    now = datetime.now()
    month = int(request.args.get("month", now.month))
    year = int(request.args.get("year", now.year))
    return jsonify(database.get_calendar_data(year, month))

@app.route("/status", methods=["GET"])
def status():
    # Deprecated for AbilityOS UI but kept for compatibility or just return empty
    # AbilityOS uses /ability_state primarily
    return jsonify({})

@app.route("/dashboard", methods=["GET"])
def dashboard():
    try:
        with open(DASHBOARD_HTML_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error loading dashboard: {e}", 500


def heartbeat_watcher():
    """Background thread that shuts down the server if no heartbeats are received."""
    log(f" >> Auto-shutdown watcher started (Timeout: {HEARTBEAT_TIMEOUT}s)")
    while True:
        time.sleep(10)
        elapsed = time.time() - LAST_HEARTBEAT
        if elapsed > HEARTBEAT_TIMEOUT:
            log(f"[!] No heartbeat for {int(elapsed)}s. Shutting down automatically...")
            os.kill(os.getpid(), signal.SIGINT)
            break

def run_server():
    log(f" >> Flask server starting on 127.0.0.1:{SERVER_PORT}...")

    # Start the safety watcher
    watcher = threading.Thread(target=heartbeat_watcher, daemon=True)
    watcher.start()

    try:
        server = make_server("127.0.0.1", SERVER_PORT, app, threaded=True)
        log(" >> Backend server bound successfully.")
        server.serve_forever()
    except OSError as exc:
        log_exception(f"Failed to bind backend on port {SERVER_PORT}", exc)
    except Exception as exc:
        log_exception("Backend server crashed unexpectedly", exc)


if __name__ == "__main__":
    run_server()
