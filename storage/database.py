import sqlite3
import os
from datetime import datetime, timedelta

from config.settings import DB_FILE

# Rank Titles (100 Levels)
TITLES_MAP = {
    1: {"zh": "初出茅庐", "en": "Novice"},
    6: {"zh": "崭露头角", "en": "Apprentice"},
    11: {"zh": "渐入佳境", "en": "Adept"},
    16: {"zh": "融会贯通", "en": "Expert"},
    21: {"zh": "登堂入室", "en": "Professional"},
    26: {"zh": "游刃有余", "en": "Specialist"},
    31: {"zh": "炉火纯青", "en": "Master"},
    36: {"zh": "出神入化", "en": "Grandmaster"},
    41: {"zh": "登峰造极", "en": "Legendary"},
    46: {"zh": "一代宗师", "en": "Sage"},
    51: {"zh": "领域大师", "en": "Archmage"},
    56: {"zh": "技近乎道", "en": "Divine"},
    61: {"zh": "造化在手", "en": "Creator"},
    66: {"zh": "天人合一", "en": "Transcendent"},
    71: {"zh": "化境", "en": "Ascended"},
    76: {"zh": "无我", "en": "Void"},
    81: {"zh": "破界", "en": "Limit Breaker"},
    86: {"zh": "觉醒", "en": "Awakened"},
    91: {"zh": "传说", "en": "Mythic"},
    96: {"zh": "不可名状", "en": "Eldritch"},
    100: {"zh": "超凡入圣", "en": "Godlike"}
}

def get_title(level):
    best = TITLES_MAP[1]
    sorted_keys = sorted(TITLES_MAP.keys())
    for threshold in sorted_keys:
        if level >= threshold:
            best = TITLES_MAP[threshold]
        else:
            break
    return best

# ASE Configuration (Level 1-10)
ASE_LEVELS = {
    1: {"target": 15, "min": 10, "max": 20},
    2: {"target": 20, "min": 15, "max": 30},
    3: {"target": 30, "min": 20, "max": 45},
    4: {"target": 45, "min": 30, "max": 60},
    5: {"target": 60, "min": 45, "max": 90},
    6: {"target": 90, "min": 60, "max": 120},
    7: {"target": 120, "min": 90, "max": 150},
    8: {"target": 150, "min": 120, "max": 180},
    9: {"target": 180, "min": 150, "max": 240},
    10: {"target": 240, "min": 180, "max": 300}
}


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    print(" >> Connecting to Database: " + DB_FILE)
    try:
        conn = get_db_connection()
        print(" >> Running SQL Migrations/Updates...")
        with conn:
            # 1. Create New Tables (If not exist)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    goal_min INTEGER DEFAULT 15,
                    created_at TEXT,
                    dimension TEXT DEFAULT 'Language',
                    level INTEGER DEFAULT 1,
                    exp INTEGER DEFAULT 0,
                    weight REAL DEFAULT 1.0,
                    streak_count INTEGER DEFAULT 0
                );
            """)
            
            # Schema Migration
            try:
                conn.execute("SELECT streak_count FROM task_config LIMIT 1")
            except sqlite3.OperationalError:
                print("Migration: Adding streak_count to task_config...")
                try: conn.execute("ALTER TABLE task_config ADD COLUMN streak_count INTEGER DEFAULT 0"); 
                except: pass
            
            try:
                conn.execute("SELECT level FROM task_config LIMIT 1")
            except sqlite3.OperationalError:
                try:
                    conn.execute("ALTER TABLE task_config ADD COLUMN level INTEGER DEFAULT 1")
                    conn.execute("ALTER TABLE task_config ADD COLUMN exp INTEGER DEFAULT 0")
                    conn.execute("ALTER TABLE task_config ADD COLUMN weight REAL DEFAULT 1.0")
                except: pass

            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_logs (
                    date TEXT,
                    task_id INTEGER,
                    seconds INTEGER DEFAULT 0,
                    PRIMARY KEY (date, task_id),
                    FOREIGN KEY(task_id) REFERENCES task_config(id)
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS ability_state (
                    dimension TEXT PRIMARY KEY,
                    last_settled_date TEXT
                );
            """)
            
            cur = conn.execute("SELECT COUNT(*) FROM ability_state")
            if cur.fetchone()[0] == 0:
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                for dim in ["Math", "Algorithm", "Coding", "Project", "Language"]:
                    conn.execute("INSERT OR IGNORE INTO ability_state (dimension, last_settled_date) VALUES (?, ?)", (dim, yesterday))
            
        conn.close()
    except Exception as e:
        print(f" !! Database Initialization Error: {e}")
        import traceback
        traceback.print_exc()


# --- Task Management ---

def get_tasks():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM task_config").fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_task(name, keyword, goal_min, dimension, weight=1.0):
    if not dimension: dimension = "General"
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO task_config (name, keyword, goal_min, created_at, dimension, level, exp, weight, streak_count) 
            VALUES (?, ?, ?, ?, ?, 1, 0, ?, 0)
        """, (name, keyword, goal_min, datetime.now().strftime("%Y-%m-%d"), dimension, weight))
        
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        conn.execute("INSERT OR IGNORE INTO ability_state (dimension, last_settled_date) VALUES (?, ?)", (dimension, yesterday))
    conn.close()

def get_all_dimensions():
    conn = get_db_connection()
    rows = conn.execute("SELECT dimension FROM ability_state").fetchall()
    conn.close()
    return [r['dimension'] for r in rows]

def delete_task(task_id):
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM task_config WHERE id = ?", (task_id,))
        conn.execute("DELETE FROM daily_logs WHERE task_id = ?", (task_id,))
    conn.close()

def delete_dimension(dim_name, force=False):
    conn = get_db_connection()
    try:
        with conn:
            count = conn.execute("SELECT COUNT(*) FROM task_config WHERE dimension = ?", (dim_name,)).fetchone()[0]
            if count == 0 or force:
                if count > 0 and force:
                    tasks = conn.execute("SELECT id FROM task_config WHERE dimension = ?", (dim_name,)).fetchall()
                    for t in tasks:
                        conn.execute("DELETE FROM daily_logs WHERE task_id = ?", (t['id'],))
                    conn.execute("DELETE FROM task_config WHERE dimension = ?", (dim_name,))
                conn.execute("DELETE FROM ability_state WHERE dimension = ?", (dim_name,))
                return True
    finally:
        conn.close()
    return False

# --- Logging & Progress ---
def update_task_progress(date_str, task_keyword, seconds):
    conn = get_db_connection()
    with conn:
        task_row = conn.execute("SELECT id FROM task_config WHERE keyword = ?", (task_keyword,)).fetchone()
        if not task_row:
            return 0
            
        task_id = task_row['id']
        
        cursor = conn.execute("SELECT seconds FROM daily_logs WHERE date = ? AND task_id = ?", (date_str, task_id))
        row = cursor.fetchone()
        current_seconds = row['seconds'] if row else 0
        if not row:
            conn.execute("INSERT INTO daily_logs (date, task_id, seconds) VALUES (?, ?, 0)", (date_str, task_id))
            
        new_seconds = current_seconds + seconds
        conn.execute("UPDATE daily_logs SET seconds = ? WHERE date = ? AND task_id = ?", (new_seconds, date_str, task_id))
            
    conn.close()
    return new_seconds

def get_daily_progress(date_str):
    conn = get_db_connection()
    # Left join to get all tasks even if no logs today
    rows = conn.execute("""
        SELECT t.*, COALESCE(l.seconds, 0) as seconds
        FROM task_config t
        LEFT JOIN daily_logs l ON t.id = l.task_id AND l.date = ?
    """, (date_str,)).fetchall()
    conn.close()
    results = []
    for row in rows:
        d = dict(row)
        # Real-time XP/Status injection
        # Note: ASE uses streaks, but maybe for legacy display we keep exp calc? 
        # Actually logic is moved to check_and_settle.
        # But UI might still look for 'exp' if I didn't fully clean it?
        # Let's keep the exp calc for safety but use .get
        d['exp'] = (d.get('exp') or 0) + int(d['seconds'] / 60)
        
        # Real-time Streak Preview (Pending Settlement)
        today_mins = int(d['seconds'] / 60)
        if today_mins >= d['goal_min']:
            s = d.get('streak_count', 0)
            if s < 0: d['streak_count'] = 1
            else: d['streak_count'] = s + 1
        
        results.append(d)
    return results

    return results


def calculate_phase(total_minutes):
    """
    Calculates Phase based on Total Minutes.
    Curve: Lvl 1 = 30m. Increase 10m per level.
    Returns: (Level, ProgressInLevel, LevelCost)
    """
    level = 1
    cost = 30
    while level < 100:
        if total_minutes >= cost:
            total_minutes -= cost
            level += 1
            cost = 30 + (level - 1) * 10
        else:
            break
    return level, total_minutes, cost

def get_ability_state():
    """
    v1.2: Decoupled Logic.
    - Task Levels (Avg) -> Difficulty Indicator (Secondary)
    - Total Minutes -> Ability Phase (Primary RPG Level)
    """
    # 1. Settle first (Task Level Updates)
    check_and_settle()
    
    conn = get_db_connection()
    
    # 1. Get GLOBAL Total Minutes per Dimension
    dim_sums = conn.execute("""
        SELECT t.dimension, SUM(l.seconds) as total_sec 
        FROM daily_logs l 
        JOIN task_config t ON l.task_id = t.id 
        GROUP BY t.dimension
    """).fetchall()
    dim_total_map = {r['dimension']: int(r['total_sec']/60) for r in dim_sums}
    
    # 2. Get Tasks (for detail list and weights)
    tasks = conn.execute("SELECT * FROM task_config").fetchall()
    
    # 3. Get today's progress (already in daily_logs usually, but just for breakdown)
    today_str = datetime.now().strftime("%Y-%m-%d")
    progress_rows = conn.execute("SELECT task_id, seconds FROM daily_logs WHERE date=?", (today_str,)).fetchall()
    progress_map = {r['task_id']: r['seconds'] for r in progress_rows}
    
    # Group by Dimension
    dims_rows = conn.execute("SELECT dimension FROM ability_state").fetchall()
    all_dims = [r['dimension'] for r in dims_rows]
    dim_data = {d: {"tasks": [], "total_weight": 0, "weighted_level_sum": 0} for d in all_dims}
    
    for t in tasks:
        d = t['dimension']
        if d not in dim_data: continue
        
        t_dict = dict(t)
        t_dict['today_seconds'] = progress_map.get(t['id'], 0)
        t_dict['today_mins'] = int(t_dict['today_seconds'] / 60)
        
        # Real-time Streak Preview
        if t_dict['today_mins'] >= t['goal_min']:
            s = t_dict.get('streak_count', 0)
            if s < 0: t_dict['streak_count'] = 1
            else: t_dict['streak_count'] = s + 1
        
        dim_data[d]["tasks"].append(t_dict)
        
    # Calculate Aggregates
    results = {}
    for dim, data in dim_data.items():
        # Phase Calculation (Based on Total History)
        total_mins = dim_total_map.get(dim, 0)
        phase, prog, cost = calculate_phase(total_mins)
        
        results[dim] = {
            "level": phase,        # The RPG Phase (1-100)
            "titles": get_title(phase),
            "tasks": data["tasks"],
            
            # Phase Progress Info
            "phase_progress": prog,    # mins into current phase
            "phase_cost": cost,        # total mins needed for this phase
            "chart_level": phase + (prog / cost if cost else 1), # Fractional level for smooth charts
            "total_accumulated": total_mins # Grand total life time
        }
    
    conn.close()
    return results

def check_and_settle():
    """
    ASE Settlement Logic (Midnight):
    - Adjusted Goal (+/- 5min)
    - Streak Update (3/-3 threshold for Level Change)
    """
    conn = get_db_connection()
    row = conn.execute("SELECT last_settled_date FROM ability_state LIMIT 1").fetchone()
    if not row: return
    
    last_date = datetime.strptime(row['last_settled_date'], "%Y-%m-%d")
    yesterday = datetime.now() - timedelta(days=1)
    
    if last_date.date() >= yesterday.date():
        conn.close()
        return

    current_check = last_date + timedelta(days=1)
    
    with conn:
        while current_check.date() <= yesterday.date():
            check_str = current_check.strftime("%Y-%m-%d")
            
            # 1. Get Usage
            logs = conn.execute("SELECT task_id, seconds FROM daily_logs WHERE date = ?", (check_str,)).fetchall()
            log_map = {l['task_id']: l['seconds'] for l in logs}
            
            # 2. Get Tasks
            tasks = conn.execute("SELECT * FROM task_config").fetchall()
            
            for t in tasks:
                tid = t['id']
                lvl = t['level']
                goal_min = t['goal_min']
                streak = t['streak_count']
                
                # Config for current level (fallback to 1 if missing)
                cfg = ASE_LEVELS.get(lvl, ASE_LEVELS[1])
                
                actual_min = int(log_map.get(tid, 0) / 60)
                
                if actual_min >= goal_min:
                    # Success
                    if streak < 0: streak = 1
                    else: streak += 1
                    
                    # Adaptive Goal: +5, capped by Level Max
                    goal_min = min(goal_min + 5, cfg['max'])
                    
                    # Level Up Check
                    if streak >= 3:
                        if lvl < 10:
                            lvl += 1
                            streak = 0
                            goal_min = ASE_LEVELS[lvl]['target'] # Reset to new target
                        else:
                            # Max Level, just keep streak?
                            pass
                else:
                    # Fail
                    if streak > 0: streak = -1
                    else: streak -= 1
                    
                    # Adaptive Goal: -5, floored by Level Min
                    goal_min = max(goal_min - 5, cfg['min'])
                    
                    # Level Down Check
                    if streak <= -3:
                        if lvl > 1:
                            lvl -= 1
                            streak = 0
                            goal_min = ASE_LEVELS[lvl]['target']
                        else:
                            pass # Min Level
                            
                # Update Task
                conn.execute("UPDATE task_config SET level=?, streak_count=?, goal_min=? WHERE id=?", (lvl, streak, goal_min, tid))
            
            # Update Settlement Date
            conn.execute("UPDATE ability_state SET last_settled_date = ?", (check_str,))
            current_check += timedelta(days=1)
            
    conn.close()
    
def get_calendar_data(year, month):
    # v1.1 Calendar: Show Star if >= 3 tasks done that day
    conn = get_db_connection()
    query_month = f"{year}-{month:02d}"
    
    logs = conn.execute("""
        SELECT l.date, count(distinct l.task_id) as tasks_met
        FROM daily_logs l
        JOIN task_config t ON l.task_id = t.id
        WHERE strftime('%Y-%m', date) = ?
          AND l.seconds >= (t.goal_min * 60)
        GROUP BY l.date
    """, (query_month,)).fetchall()
    
    results = {}
    for r in logs:
        d = r['date']
        count = r['tasks_met']
        if count >= 3:
            results[d] = "star"
        elif count > 0:
            results[d] = "partial"
            
    conn.close()
    return results

def get_history():
    # v1.1 History: We want global ability levels over time?
    # Or just minutes?
    # Existing `history.json` logic should ideally look at snapshots.
    # But for MVP, we'll return daily minutes per dimension.
    
    conn = get_db_connection()
    logs = conn.execute("""
        SELECT l.date, t.dimension, SUM(l.seconds) as total_seconds
        FROM daily_logs l
        JOIN task_config t ON l.task_id = t.id
        GROUP BY l.date, t.dimension
        ORDER BY l.date ASC
    """).fetchall()
    
    pivot = {}
    for row in logs:
        d = row['date']
        dim = row['dimension']
        s = row['total_seconds']
        if d not in pivot: pivot[d] = {"date": d}
        pivot[d][dim] = s
        
    conn.close()
    return list(pivot.values())

