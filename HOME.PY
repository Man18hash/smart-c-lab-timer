import json
import os
import sys
import subprocess
from datetime import timedelta
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

import tkinter as tk
from tkinter import ttk, messagebox

# ========== CONFIG ==========
CONFIG_PATH = Path("kiosk_timer_config.json")
DEFAULT_CONFIG = {
    "countdown_seconds": 15 * 60,   # default 15 minutes
    "laptop_details": "Laptop 1 (editable in Admin)\nBrand:\nModel:\nAsset Tag:\nUser:",
    "override_ip": "",
    "override_location": ""
}
ADMIN_USER = "admin"
ADMIN_PASS = "123"

# ========== STORAGE ==========
def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    data.setdefault(k, v)
                return data
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print("Failed to save config:", e)

# ========== NETWORK HELPERS ==========
def get_public_ip():
    urls = ["https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"]
    for u in urls:
        try:
            with urlopen(u, timeout=5) as resp:
                return resp.read().decode().strip()
        except URLError:
            continue
        except Exception:
            continue
    return "Unknown"

def get_location_for_ip(ip):
    if not ip or ip == "Unknown":
        return "Unknown"
    services = [
        f"https://ipapi.co/{ip}/city/",
        f"https://ipapi.co/{ip}/region/",
        f"https://ipapi.co/{ip}/country_name/",
    ]
    parts = []
    for s in services:
        try:
            with urlopen(s, timeout=5) as resp:
                val = resp.read().decode().strip()
                if val and "error" not in val.lower():
                    parts.append(val)
                else:
                    parts.append("")
        except Exception:
            parts.append("")
    city = parts[0] if len(parts) > 0 else ""
    region = parts[1] if len(parts) > 1 else ""
    country = parts[2] if len(parts) > 2 else ""
    text = ", ".join([p for p in (city, region, country) if p])
    return text if text else "Unknown"

# ========== OS LOGOUT ==========
def attempt_logout():
    try:
        if sys.platform.startswith("win"):
            subprocess.run(["shutdown", "/l"], check=False)
            return True
        elif sys.platform == "darwin":
            script = 'tell application "System Events" to log out'
            subprocess.run(["osascript", "-e", script], check=False)
            return True
        else:
            # Linux
            res = subprocess.run(["gnome-session-quit", "--logout", "--no-prompt"], check=False)
            if res.returncode == 0:
                return True
            uid = os.getuid()
            subprocess.run(["loginctl", "terminate-user", str(uid)], check=False)
            return True
    except Exception as e:
        print("Logout attempt error:", e)
        return False

# ========== UI COMPONENTS ==========
class FullscreenAlert(tk.Toplevel):
    def __init__(self, master, message="Timer is done — return this laptop"):
        super().__init__(master)
        self.title("Time's Up")
        self.attributes("-topmost", True)
        self.attributes("-fullscreen", True)
        self.configure(bg="#0b1220")  # deep slate
        self.bind("<Escape>", lambda e: None)  # block Esc

        wrapper = tk.Frame(self, bg="#0b1220")
        wrapper.pack(expand=True, fill="both")

        lbl = tk.Label(
            wrapper, text=message, fg="#ffffff", bg="#0b1220",
            font=("Segoe UI", 40, "bold"), wraplength=1400, justify="center"
        )
        lbl.pack(pady=30)

        sub = tk.Label(
            wrapper, text="Please return this laptop to the administrator.",
            fg="#a3b2d1", bg="#0b1220", font=("Segoe UI", 20)
        )
        sub.pack(pady=8)

        btn = ttk.Button(wrapper, text="I understand", command=self.close)
        btn.pack(pady=24)

        try:
            self.grab_set()
            self.focus_force()
        except Exception:
            pass

    def close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

class Section(ttk.Frame):
    def __init__(self, parent, title):
        super().__init__(parent)
        card = tk.Frame(self, bg="#121a2b", bd=0, highlightthickness=0)
        card.pack(fill="both", expand=True)

        head = tk.Frame(card, bg="#121a2b")
        head.pack(fill="x", padx=16, pady=(14, 2))
        tk.Label(head, text=title, bg="#121a2b", fg="#e4ebff",
                 font=("Segoe UI", 12, "bold")).pack(anchor="w")

        sep = tk.Frame(card, bg="#1e2a44", height=1)
        sep.pack(fill="x", padx=16, pady=(6, 8))

        self.body = tk.Frame(card, bg="#121a2b")
        self.body.pack(fill="both", expand=True, padx=16, pady=(0, 14))

# ========== DASHBOARD ==========
class Dashboard(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.bg = tk.Frame(self, bg="#0b1220")
        self.bg.pack(fill="both", expand=True)

        header = tk.Frame(self.bg, bg="#0b1220")
        header.pack(fill="x", pady=(12, 0), padx=16)

        tk.Label(header, text="Device Timer", bg="#0b1220", fg="#dce7ff",
                 font=("Segoe UI", 14, "bold")).pack(side="left")

        self.admin_btn = ttk.Button(header, text="Admin",
                                    command=self.app.handle_admin_button_from_dashboard)
        self.admin_btn.pack(side="right")

        card = tk.Frame(self.bg, bg="#121a2b")
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # Big Timer
        timer_wrap = tk.Frame(card, bg="#121a2b")
        timer_wrap.pack(fill="x", pady=(28, 8))
        self.timer_var = tk.StringVar(value="00:00:00")
        tk.Label(timer_wrap, textvariable=self.timer_var, bg="#121a2b", fg="#ffffff",
                 font=("Segoe UI", 64, "bold")).pack(anchor="center")

        # Location + IP
        info_wrap = tk.Frame(card, bg="#121a2b")
        info_wrap.pack(fill="x", pady=(10, 4))
        self.loc_var = tk.StringVar(value="Location: Loading…")
        self.ip_var = tk.StringVar(value="IP: Loading…")
        tk.Label(info_wrap, textvariable=self.loc_var, bg="#121a2b", fg="#a3b2d1",
                 font=("Segoe UI", 13)).pack(anchor="center", pady=2)
        tk.Label(info_wrap, textvariable=self.ip_var, bg="#121a2b", fg="#a3b2d1",
                 font=("Segoe UI", 13)).pack(anchor="center", pady=2)

        # Laptop details (read-only)
        details_wrap = tk.Frame(card, bg="#121a2b")
        details_wrap.pack(fill="both", expand=True, pady=(18, 24), padx=16)

        tk.Label(details_wrap, text="Laptop Details", bg="#121a2b", fg="#e4ebff",
                 font=("Segoe UI", 12, "bold")).pack(anchor="w")

        self.details = tk.Text(details_wrap, width=80, height=10, bd=0, relief="flat",
                               bg="#0f1628", fg="#d6e2ff", insertbackground="#d6e2ff",
                               font=("Segoe UI", 11), wrap="word")
        self.details.pack(fill="both", expand=True, pady=(8, 0))
        self.details.insert("1.0", self.app.config_data.get("laptop_details", ""))
        self.details.configure(state="disabled")

    def set_timer(self, seconds_left):
        td = str(timedelta(seconds=max(0, int(seconds_left))))
        if len(td.split(":")) == 2:  # ensure HH:MM:SS
            td = "0:" + td
        self.timer_var.set(td)

    def refresh_ip_location(self):
        cfg = self.app.config_data
        if cfg.get("override_ip"):
            ip = cfg["override_ip"]
        else:
            ip = get_public_ip()
        if cfg.get("override_location"):
            loc = cfg["override_location"]
        else:
            loc = get_location_for_ip(ip) if ip != "Unknown" else "Unknown"
        self.ip_var.set(f"IP: {ip}")
        self.loc_var.set(f"Location: {loc}")

    def refresh_laptop_details(self):
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", self.app.config_data.get("laptop_details", ""))
        self.details.configure(state="disabled")

# ========== ADMIN VIEW ==========
class AdminView(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.bg = tk.Frame(self, bg="#0b1220")
        self.bg.pack(fill="both", expand=True)

        header = tk.Frame(self.bg, bg="#0b1220")
        header.pack(fill="x", pady=(12, 0), padx=16)

        tk.Label(header, text="Admin Panel", bg="#0b1220", fg="#dce7ff",
                 font=("Segoe UI", 14, "bold")).pack(side="left")

        # Right-side actions
        actions = tk.Frame(header, bg="#0b1220")
        actions.pack(side="right")
        ttk.Button(actions, text="View Dashboard", command=self.app.show_dashboard).pack(side="left", padx=6)
        ttk.Button(actions, text="Sign Out", command=self.app.sign_out_admin).pack(side="left")

        outer = ttk.Frame(self.bg, padding=18)
        outer.pack(fill="both", expand=True)

        # Timer Controls
        sec_timer = Section(outer, "Timer Controls")
        sec_timer.pack(fill="x", pady=(0, 12))

        row = ttk.Frame(sec_timer.body)
        row.pack(fill="x", pady=6)
        ttk.Label(row, text="Countdown (minutes)").pack(side="left")
        self.minutes_var = tk.StringVar(value=str(max(1, self.app.config_data["countdown_seconds"] // 60)))
        ttk.Entry(row, width=10, textvariable=self.minutes_var).pack(side="left", padx=8)

        state_row = ttk.Frame(sec_timer.body)
        state_row.pack(fill="x", pady=6)
        self.state_var = tk.StringVar(value=self.app.state_text())
        ttk.Label(state_row, textvariable=self.state_var).pack(side="left")

        ctrl_row = ttk.Frame(sec_timer.body)
        ctrl_row.pack(fill="x", pady=8)
        ttk.Button(ctrl_row, text="Start", command=self._start).pack(side="left")
        ttk.Button(ctrl_row, text="Pause", command=self._pause).pack(side="left", padx=6)
        ttk.Button(ctrl_row, text="Reset to Saved", command=self._reset_to_saved).pack(side="left", padx=6)
        ttk.Button(ctrl_row, text="Save Minutes", command=self._save_minutes).pack(side="left", padx=6)

        # Network Overrides
        sec_net = Section(outer, "Network Overrides (optional)")
        sec_net.pack(fill="x", pady=(0, 12))

        net_form = ttk.Frame(sec_net.body)
        net_form.pack(fill="x", pady=6)
        ttk.Label(net_form, text="Override IP").grid(row=0, column=0, sticky="w")
        self.ip_var = tk.StringVar(value=self.app.config_data.get("override_ip", ""))
        ttk.Entry(net_form, textvariable=self.ip_var, width=30).grid(row=0, column=1, sticky="w", padx=8)

        ttk.Label(net_form, text="Override Location").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.loc_var = tk.StringVar(value=self.app.config_data.get("override_location", ""))
        ttk.Entry(net_form, textvariable=self.loc_var, width=40).grid(row=1, column=1, sticky="w", padx=8, pady=(6, 0))

        ttk.Button(sec_net.body, text="Save Network Overrides", command=self._save_net).pack(pady=6)

        # Laptop Details
        sec_lap = Section(outer, "Laptop 1 Details")
        sec_lap.pack(fill="both", expand=True)

        self.details_txt = tk.Text(sec_lap.body, width=56, height=8)
        self.details_txt.pack(fill="both", expand=True)
        self.details_txt.insert("1.0", self.app.config_data.get("laptop_details", ""))

        ttk.Button(sec_lap.body, text="Save Details", command=self._save_details).pack(pady=8)

        self.update_state_text()

    def update_state_text(self):
        self.state_var.set(self.app.state_text())

    # --- Admin actions ---
    def _start(self):
        if self.app.seconds_left <= 0:
            self.app.seconds_left = self.app.config_data["countdown_seconds"]
        self.app.start_timer()
        self.update_state_text()

    def _pause(self):
        self.app.pause_timer()
        self.update_state_text()

    def _reset_to_saved(self):
        self.app.reset_to_saved()
        self.update_state_text()

    def _save_minutes(self):
        try:
            mins = int(self.minutes_var.get().strip())
            if mins <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid value", "Minutes must be a positive integer.")
            return
        self.app.config_data["countdown_seconds"] = mins * 60
        save_config(self.app.config_data)
        self.app.seconds_left = self.app.config_data["countdown_seconds"]
        self.app.pause_timer()
        self.update_state_text()
        messagebox.showinfo("Saved", "Countdown minutes saved.")

    def _save_net(self):
        self.app.config_data["override_ip"] = self.ip_var.get().strip()
        self.app.config_data["override_location"] = self.loc_var.get().strip()
        save_config(self.app.config_data)
        self.app.refresh_ip_location()
        messagebox.showinfo("Saved", "Network overrides saved.")

    def _save_details(self):
        self.app.config_data["laptop_details"] = self.details_txt.get("1.0", "end").strip()
        save_config(self.app.config_data)
        self.app.refresh_laptop_details()
        messagebox.showinfo("Saved", "Laptop details saved.")

# ========== LOGIN DIALOG ==========
class LoginDialog(tk.Toplevel):
    def __init__(self, master, on_success):
        super().__init__(master)
        self.title("Admin Login")
        self.resizable(False, False)

        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Username").grid(row=0, column=0, sticky="w")
        self.user_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.user_var, width=28).grid(row=0, column=1, padx=8, pady=4)

        ttk.Label(frm, text="Password").grid(row=1, column=0, sticky="w")
        self.pass_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.pass_var, width=28, show="•").grid(row=1, column=1, padx=8, pady=4)

        buttons = ttk.Frame(frm)
        buttons.grid(row=2, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Login",
                   command=lambda: self._try(on_success)).pack(side="right", padx=6)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")

        self.bind("<Return>", lambda e: self._try(on_success))
        self.after(120, lambda: self.focus_force())

    def _try(self, on_success):
        if self.user_var.get() == ADMIN_USER and self.pass_var.get() == ADMIN_PASS:
            on_success()
            self.destroy()
        else:
            messagebox.showerror("Login failed", "Invalid credentials.")

# ========== APP ==========
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Kiosk Timer")
        self.geometry("900x640")
        self.minsize(820, 560)

        # Modern ttk tweaks
        self._init_style()

        self.config_data = load_config()
        self.seconds_left = self.config_data["countdown_seconds"]
        self._counting = False
        self._session_is_admin = False  # <-- admin session flag

        # Views
        self.container = tk.Frame(self, bg="#0b1220")
        self.container.pack(fill="both", expand=True)

        self.dashboard = Dashboard(self.container, self)
        self.admin_view = AdminView(self.container, self)

        # Start on dashboard
        self.show_dashboard()

        # initial data
        self.dashboard.set_timer(self.seconds_left)
        self.refresh_ip_location()

        # heartbeat
        self._pulse()

    # ---- Styling ----
    def _init_style(self):
        try:
            self.call("tk", "scaling", 1.2)
        except Exception:
            pass
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TButton",
                        padding=(12, 8),
                        font=("Segoe UI", 10, "bold"),
                        foreground="#e9efff",
                        background="#28406d",
                        borderwidth=0)
        style.map("TButton",
                  foreground=[("active", "#ffffff")],
                  background=[("active", "#355591")])
        style.configure("TLabel", foreground="#dce7ff", background="#121a2b")
        style.configure("TFrame", background="#0b1220")

    # ---- View switching ----
    def show_dashboard(self):
        self.admin_view.pack_forget()
        self.dashboard.pack(fill="both", expand=True)

    def show_admin(self):
        self.dashboard.pack_forget()
        self.admin_view.pack(fill="both", expand=True)

    # ---- Session flow ----
    def handle_admin_button_from_dashboard(self):
        if self._session_is_admin:
            self.show_admin()  # already authenticated; no re-login
        else:
            LoginDialog(self, on_success=self._admin_login_success)

    def _admin_login_success(self):
        self._session_is_admin = True
        self.show_admin()

    def sign_out_admin(self):
        self._session_is_admin = False
        self.show_dashboard()

    # ---- Dashboard/Admin shared helpers ----
    def refresh_ip_location(self):
        self.dashboard.refresh_ip_location()

    def refresh_laptop_details(self):
        self.dashboard.refresh_laptop_details()

    # ---- Timer Engine ----
    def start_timer(self):
        if self.seconds_left <= 0:
            self.seconds_left = self.config_data["countdown_seconds"]
        self._counting = True

    def pause_timer(self):
        self._counting = False

    def reset_to_saved(self):
        self.pause_timer()
        self.seconds_left = self.config_data["countdown_seconds"]
        self.dashboard.set_timer(self.seconds_left)

    def _tick_once(self):
        if self._counting:
            if self.seconds_left <= 0:
                self._counting = False
                self._on_timer_done()
            else:
                self.seconds_left -= 1
                self.dashboard.set_timer(self.seconds_left)

    def _pulse(self):
        self._tick_once()
        self.after(1000, self._pulse)

    def _on_timer_done(self):
        attempted = attempt_logout()
        FullscreenAlert(self, message="Timer is done — return this laptop")
        if not attempted:
            messagebox.showinfo("Timer Finished",
                                "Logout may not be supported on this system. A full-screen alert was shown.")

    # ---- State text for admin ----
    def state_text(self):
        state = "Running" if self._counting else "Paused/Stopped"
        td = self._fmt(self.seconds_left)
        return f"State: {state}   |   Remaining: {td}"

    @staticmethod
    def _fmt(s):
        td = str(timedelta(seconds=max(0, int(s))))
        if len(td.split(":")) == 2:
            td = "0:" + td
        return td

if __name__ == "__main__":
    app = App()
    app.mainloop()
