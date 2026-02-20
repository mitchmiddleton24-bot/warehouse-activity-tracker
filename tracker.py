r"""
Warehouse Activity Tracker
--------------------------
Silently tracks the first and last keyboard/mouse activity of each day.
Logs to C:\WarehouseTracker\activity_log.csv (Date, First Activity, Last Activity).
- CSV is flushed every 15 minutes so data survives a hard shutdown.
- Also flushed on day rollover and on clean exit.
- Adds itself to the Windows registry for auto-start on login.
- Shows a system tray icon with a right-click menu.
"""

import csv
import os
import sys
import threading
import winreg
from datetime import datetime
from pathlib import Path

import pystray
from PIL import Image, ImageDraw
from pynput import keyboard, mouse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LOG_DIR = Path(r"C:\WarehouseTracker")
LOG_FILE = LOG_DIR / "activity_log.csv"
CSV_COLUMNS = ["Date", "First Activity", "Last Activity"]

APP_NAME = "WarehouseActivityTracker"
FLUSH_INTERVAL_SECONDS = 15 * 60  # 15 minutes
DATE_CHECK_INTERVAL_SECONDS = 60   # check for midnight rollover every minute

# ---------------------------------------------------------------------------
# State (protected by a lock for thread safety)
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_current_date: str = ""          # "YYYY-MM-DD"
_first_activity: datetime | None = None
_last_activity: datetime | None = None


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------
def _ensure_log_file() -> None:
    """Create the log directory and CSV header if they don't exist."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE.exists():
        with open(LOG_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()


def _fmt(dt: datetime | None) -> str:
    return dt.strftime("%H:%M:%S") if dt else ""


def _flush_today() -> None:
    """
    Write (or update) today's row in the CSV.
    Each flush rewrites the entire file so the current day's row reflects
    the latest Last Activity without growing duplicates.
    """
    with _lock:
        date = _current_date
        first = _first_activity
        last = _last_activity

    if not date:
        return

    _ensure_log_file()

    # Read all existing rows
    rows: list[dict] = []
    if LOG_FILE.exists():
        with open(LOG_FILE, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

    # Update or append today's row
    updated = False
    for row in rows:
        if row["Date"] == date:
            row["First Activity"] = _fmt(first)
            row["Last Activity"] = _fmt(last)
            updated = True
            break
    if not updated:
        rows.append({
            "Date": date,
            "First Activity": _fmt(first),
            "Last Activity": _fmt(last),
        })

    # Rewrite the file atomically via a temp file
    tmp = LOG_FILE.with_suffix(".tmp")
    with open(tmp, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(LOG_FILE)


# ---------------------------------------------------------------------------
# Activity recording
# ---------------------------------------------------------------------------
def _record_activity() -> None:
    """Called on every mouse/keyboard event."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    with _lock:
        global _current_date, _first_activity, _last_activity

        if _current_date != today:
            # Day has rolled over — flush previous day and reset
            if _current_date:
                # flush the old day (must release lock to call _flush_today)
                pass  # handled by date-check thread; just reset here
            _current_date = today
            _first_activity = now
            _last_activity = now
        else:
            if _first_activity is None:
                _first_activity = now
            _last_activity = now


# ---------------------------------------------------------------------------
# Background threads
# ---------------------------------------------------------------------------
def _periodic_flush_thread() -> None:
    """Flush CSV every FLUSH_INTERVAL_SECONDS."""
    flush_event = threading.Event()
    while not flush_event.wait(FLUSH_INTERVAL_SECONDS):
        _flush_today()


def _date_rollover_thread() -> None:
    """Detect midnight rollover and flush the previous day's data."""
    rollover_event = threading.Event()
    last_known_date = datetime.now().strftime("%Y-%m-%d")
    while not rollover_event.wait(DATE_CHECK_INTERVAL_SECONDS):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != last_known_date:
            # Flush previous day before state resets
            _flush_today()
            with _lock:
                global _current_date, _first_activity, _last_activity
                _current_date = today
                _first_activity = None
                _last_activity = None
            last_known_date = today


# ---------------------------------------------------------------------------
# Windows auto-start (HKCU — no admin required)
# ---------------------------------------------------------------------------
def _register_autostart() -> None:
    exe = sys.executable if not getattr(sys, "frozen", False) else sys.executable
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe}"')
    except OSError:
        pass  # Non-fatal; app still works without auto-start


# ---------------------------------------------------------------------------
# System tray icon
# ---------------------------------------------------------------------------
def _make_icon_image() -> Image.Image:
    """Draw a simple green circle icon (32×32)."""
    size = 32
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 2
    # Outer circle (dark green border)
    draw.ellipse([margin, margin, size - margin, size - margin], fill="#2e7d32")
    # Inner highlight
    inner = margin + 5
    draw.ellipse([inner, inner, size - inner, size - inner], fill="#66bb6a")
    return img


def _open_log_folder(icon, item) -> None:
    os.startfile(str(LOG_DIR))


def _exit_app(icon, item) -> None:
    _flush_today()
    icon.stop()


def _build_tray() -> pystray.Icon:
    menu = pystray.Menu(
        pystray.MenuItem("Open Log Folder", _open_log_folder),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", _exit_app),
    )
    return pystray.Icon(APP_NAME, _make_icon_image(), "Warehouse Tracker", menu)


# ---------------------------------------------------------------------------
# pynput listeners
# ---------------------------------------------------------------------------
def _on_keyboard_press(key) -> None:
    _record_activity()


def _on_mouse_move(x, y) -> None:
    _record_activity()


def _on_mouse_click(x, y, button, pressed) -> None:
    if pressed:
        _record_activity()


def _on_mouse_scroll(x, y, dx, dy) -> None:
    _record_activity()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    # Initialise state for today
    global _current_date
    _current_date = datetime.now().strftime("%Y-%m-%d")

    _ensure_log_file()
    _register_autostart()

    # Start background threads (daemon so they die with main thread)
    threading.Thread(target=_periodic_flush_thread, daemon=True).start()
    threading.Thread(target=_date_rollover_thread, daemon=True).start()

    # Start input listeners (non-blocking)
    keyboard.Listener(on_press=_on_keyboard_press).start()
    mouse.Listener(
        on_move=_on_mouse_move,
        on_click=_on_mouse_click,
        on_scroll=_on_mouse_scroll,
    ).start()

    # Build and run the tray icon (blocks until Exit is chosen)
    tray = _build_tray()
    tray.run()


if __name__ == "__main__":
    main()
