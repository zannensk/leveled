import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
import requests
import threading
import webbrowser
import os
import shutil
import sys
import time

from utils.runtime_log import log_exception

# Configuration
SERVER_BASE = "http://127.0.0.1:5123"
REFRESH_MS = 2000

HTTP = requests.Session()
HTTP.trust_env = False


def _http_get(url, timeout=1, **kwargs):
    return HTTP.get(url, timeout=timeout, **kwargs)


def _http_post(url, timeout=1, **kwargs):
    return HTTP.post(url, timeout=timeout, **kwargs)


def _http_delete(url, timeout=1, **kwargs):
    return HTTP.delete(url, timeout=timeout, **kwargs)


class TaskOverlay:
    def __init__(self, root):
        self.root = root
        self.root.title("AbilityOS")
        
        # Window attributes
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.8)
        self.root.configure(bg="#222")
        
        # Dragging state
        self.x = 0
        self.y = 0

        
        self.root.update_idletasks() # Must run before pywinstyles
        try:
            import pywinstyles
            pywinstyles.set_window_corners(self.root, "round") # Round the corners
        except:
            pass

        
        # Geometry (auto-adjusts generally, but set init width)
        screen_width = self.root.winfo_screenwidth()
        x_pos = screen_width - 260
        y_pos = 20
        self.root.geometry(f"240x200+{x_pos}+{y_pos}")
        
        # Dragging
        self.root.bind("<Button-1>", self.start_move)
        self.root.bind("<B1-Motion>", self.do_move)
        
        # Title Bar
        title_frame = tk.Frame(self.root, bg="#333", height=25)
        title_frame.pack(fill="x")
        
        title_lbl = tk.Label(title_frame, text="Active Tasks", fg="#ddd", bg="#333", font=("Arial", 9, "bold"))
        title_lbl.pack(side="left", padx=5)
        
        btn_font = ("Arial", 12, "bold")
        
        exit_btn = tk.Label(title_frame, text="×", fg="#f44", bg="#333", font=btn_font, cursor="hand2")
        exit_btn.pack(side="right", padx=6)
        exit_btn.bind("<Button-1>", lambda e: self.close_app())
        
        add_btn = tk.Label(title_frame, text="+", fg="#4CAF50", bg="#333", font=btn_font, cursor="hand2")
        add_btn.pack(side="right", padx=6)
        add_btn.bind("<Button-1>", self.show_add_dialog)
        
        # Import Button (using a hamburger menu / identical-to symbol from the same math block as + and ×)
        import_btn = tk.Label(title_frame, text="≡", fg="#aaa", bg="#333", font=btn_font, cursor="hand2")
        import_btn.pack(side="right", padx=6)
        import_btn.bind("<Button-1>", self.import_data)

        # Main Container
        self.main_frame = tk.Frame(self.root, bg="#222")
        self.main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # State
        self.is_expanded = False
        self.widgets = {} # task_id -> frame
        self.toggle_btn = None
        
        # Start loops
        self.update_progress()
        self.keep_on_top()
        self.last_signature = None
        self.last_conn_error_log = 0

    def close_app(self):
        # 1. Open Dashboard in browser
        try:
            webbrowser.open(f"{SERVER_BASE}/dashboard")
        except: pass
        
        # 2. Kill Overlay only - server keeps running for dashboard
        self.root.destroy()

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")
        
    def keep_on_top(self):
        self.root.lift()
        self.root.after(2000, self.keep_on_top)

    def show_add_dialog(self, event):
        # Fetch current dimensions from server
        try:
            resp = _http_get(f"{SERVER_BASE}/dimensions", timeout=1)
            dimensions = resp.json()
        except:
            dimensions = ["Math", "Algorithm", "Coding", "Project", "Language"] # Fallback

        name = simpledialog.askstring("Add Task", "Task Name:", parent=self.root)
        if not name: return
        kw = simpledialog.askstring("Add Task", "URL Keyword (e.g. 'github'):", parent=self.root)
        if not kw: return
        goal = simpledialog.askinteger("Add Task", "Daily Goal (min):", parent=self.root, initialvalue=15)
        if not goal: goal = 15
        
        # New: Allow picking or typing a new dimension
        dim_prompt = "Existing Dimensions:\n" + "\n".join([f"{i+1}. {d}" for i, d in enumerate(dimensions)])
        dim_prompt += "\n\nEnter a NUMBER to select, or TYPE a NEW name:"
        
        res = simpledialog.askstring("Dimension", dim_prompt, parent=self.root)
        if not res: return
        
        selected_dim = ""
        if res.isdigit():
            idx = int(res) - 1
            if 0 <= idx < len(dimensions):
                selected_dim = dimensions[idx]
            else:
                selected_dim = res # Use as name if number is out of range
        else:
            selected_dim = res # Use as new name
            
        try:
            _http_post(f"{SERVER_BASE}/tasks", json={
                "name": name, "keyword": kw, "goal": goal, "dimension": selected_dim
            })
            self.fetch_and_update()
        except: pass


    def delete_task(self, task_id):
        if messagebox.askyesno("Delete", "Stop tracking this task?", parent=self.root):
            try:
                _http_delete(f"{SERVER_BASE}/tasks/{task_id}")
                self.fetch_and_update()
            except: pass

    def import_data(self, event):
        confirm = messagebox.askyesno("Import Data", 
            "This will overwrite current data. Do you want to select a progress.db file to import?", parent=self.root)
        if not confirm: return
        
        file_path = filedialog.askopenfilename(title="Select progress.db", filetypes=[("SQLite DB", "*.db"), ("All Files", "*.*")])
        if not file_path: return
        
        try:
            # Atomic Swap Strategy: Copy to .pending files 
            # These are NOT locked by the current process.
            target_dir = os.path.dirname(os.path.join(os.path.expanduser("~"), ".leveled", "progress.db"))
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            
            pending_db = os.path.join(target_dir, "progress.db.pending")
            shutil.copy2(file_path, pending_db)
            
            # Look for siblings
            source_dir = os.path.dirname(file_path)
            for j in ["history.json", "progress.json"]:
                s = os.path.join(source_dir, j)
                if os.path.exists(s):
                    shutil.copy2(s, os.path.join(target_dir, f"{j}.pending"))
            
            messagebox.showinfo("Import", "Data staged for import. Application will now close.\n\nPlease run start.bat again to apply changes.", parent=self.root)
            
            # Close only the overlay - server does NOT need to shut down
            import sys
            sys.exit(0)
            
        except PermissionError:
            messagebox.showerror("Error", "File is locked. Please close any other programs using the database and try again.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import data: {e}", parent=self.root)


    def update_progress(self):
        threading.Thread(target=self.fetch_and_update, daemon=True).start()
        self.root.after(REFRESH_MS, self.update_progress)
        
    def fetch_and_update(self):
        try:
            # Heartbeat to keep server alive
            _http_post(f"{SERVER_BASE}/api/heartbeat", timeout=1)
            
            resp = _http_get(f"{SERVER_BASE}/progress", timeout=1)
            resp.raise_for_status()
            data = resp.json() # [{id, name, seconds, goal_min, [dimension?]}, ...]
            self.root.after(0, lambda: self.refresh_ui(data))
        except Exception as exc:
            now = time.time()
            if now - self.last_conn_error_log > 15:
                log_exception("Overlay failed to reach backend server", exc)
                self.last_conn_error_log = now
            self.root.after(0, self.show_backend_offline)

    def show_backend_offline(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        if self.toggle_btn:
            self.toggle_btn.pack_forget()

        msg = tk.Label(
            self.main_frame,
            text="Backend offline.\nPlease restart Leveled.",
            fg="#ffb4b4",
            bg="#222",
            font=("Segoe UI", 9),
            justify="left",
            anchor="w",
        )
        msg.pack(fill="x", padx=4, pady=10)
            
    def toggle_expand(self, event):
        self.is_expanded = not self.is_expanded
        self.last_signature = None # Force refresh
        self.fetch_and_update() # Re-render

    def refresh_ui(self, tasks):
        # 1. Sort: Incomplete first, then by name
        enriched = []
        for t in tasks:
            mins = int(t['seconds'] / 60)
            goal = t['goal_min']
            is_done = mins >= goal
            enriched.append({**t, "mins": mins, "is_done": is_done})
            
        enriched.sort(key=lambda x: (x['is_done'], x['name']))
        
        # 2. Slice
        total_count = len(enriched)
        display_list = enriched
        if not self.is_expanded and total_count > 3:
            display_list = enriched[:3]
            
        # Optimization: Check if UI needs update
        # Include visual properties in signature (active status, text, etc)
        sig = str([{k: t[k] for k in ['id', 'mins', 'is_done', 'active', 'name', 'goal_min']} for t in display_list]) + str(total_count) + str(self.is_expanded)
        
        if self.last_signature == sig:
            return
        self.last_signature = sig
        
        # 3. Render
        # FIX: Use destroy() instead of pack_forget() to prevent memory leak
        for widget in self.main_frame.winfo_children():
            widget.destroy() 
            
        # Re-create widgets in order
        self.widgets = {} 
        
        for t in display_list:
            tid = t['id']
            
            # Row Frame
            f = tk.Frame(self.main_frame, bg="#222")
            f.pack(fill="x", pady=2)
            
            # Text Config
            if t.get('active'):
                txt = f"⚡ {t['name']}: {t['mins']}m"
                fg_col = "#FFD700" # Gold/Yellow for Active
            elif t['is_done']:
                txt = f"✅ {t['name']} ({t['mins']}m)"
                fg_col = "#4caf50" # Green
            else:
                txt = f"{t['name']}: {t['mins']} / {t['goal_min']}m"
                fg_col = "#eee"
                
            l = tk.Label(f, text=txt, fg=fg_col, bg="#222", font=("Segoe UI", 10), anchor="w")
            l.pack(side="left", fill="x", expand=True)
            
            # Delete Button
            d = tk.Label(f, text="×", fg="#666", bg="#222", cursor="hand2")
            d.pack(side="right", padx=5)
            d.bind("<Button-1>", lambda e, _id=tid: self.delete_task(_id))
            
        # 4. Show More / Less Button
        if total_count > 3:
            btn_txt = "Show Less ▲" if self.is_expanded else f"Show All ({total_count}) ▼"
            if not self.toggle_btn:
                self.toggle_btn = tk.Label(self.root, text=btn_txt, fg="#aaa", bg="#222", font=("Segoe UI", 8), cursor="hand2")
                self.toggle_btn.bind("<Button-1>", self.toggle_expand)
            else:
                self.toggle_btn.config(text=btn_txt)
            
            self.toggle_btn.pack(side="top", pady=5)
        else:
            if self.toggle_btn:
                self.toggle_btn.pack_forget()

        # Resize Height dynamic
        rows = len(display_list)
        h = 35 + (rows * 28) + (25 if total_count > 3 else 0) + 10
        w = self.root.winfo_width()
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.root.geometry(f"{w}x{h}+{x}+{y}")

def run_overlay():
    root = tk.Tk()
    app = TaskOverlay(root)
    root.mainloop()

if __name__ == "__main__":
    run_overlay()

