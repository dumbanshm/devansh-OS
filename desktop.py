"""Devansh OS — native desktop launcher (macOS).

Runs the FastAPI server in a background thread and presents:
  • a menu-bar item (rumps) that lives quietly and can launch at login, and
  • a native window (pywebview) opened in a separate process.

Two processes by design: the menu-bar app owns the macOS run loop, and each
window runs its own webview loop in a child process — this sidesteps the
single-main-loop limitation of combining rumps + pywebview.

Entry points:
  python desktop.py            → menu-bar app (starts server, opens a window)
  python desktop.py --window   → just a webview window onto the running server
"""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

PORT = int(os.environ.get("DEVANSH_PORT", "8770"))
HOST = "127.0.0.1"
URL = f"http://{HOST}:{PORT}/"
LABEL = "com.devansh.os"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


# ── Server ──────────────────────────────────────────────────────────────────
def start_server() -> None:
    """Run uvicorn in this thread (signal handlers disabled so it works off the
    main thread)."""
    import uvicorn

    from app.main import app

    config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[assignment]
    server.run()


def wait_ready(timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(URL + "healthz", timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def _self_cmd(*args: str) -> list[str]:
    """Command to re-invoke this app (frozen binary or python script)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, os.path.abspath(__file__), *args]


# ── Window (child process) ──────────────────────────────────────────────────
def run_window() -> None:
    import webview

    wait_ready()
    webview.create_window(
        "Devansh OS", URL, width=1500, height=950, min_size=(900, 600)
    )
    webview.start()


# ── Launch-at-login (LaunchAgent) ───────────────────────────────────────────
def login_enabled() -> bool:
    return PLIST.exists()


def set_login(enable: bool) -> None:
    if enable:
        PLIST.parent.mkdir(parents=True, exist_ok=True)
        program = _self_cmd()
        with PLIST.open("wb") as fh:
            plistlib.dump({
                "Label": LABEL,
                "ProgramArguments": program,
                "RunAtLoad": True,
                "KeepAlive": False,
            }, fh)
        subprocess.run(["launchctl", "load", str(PLIST)], check=False)
    else:
        subprocess.run(["launchctl", "unload", str(PLIST)], check=False)
        PLIST.unlink(missing_ok=True)


# ── Menu-bar app ────────────────────────────────────────────────────────────
def run_menubar() -> None:
    import rumps

    threading.Thread(target=start_server, daemon=True).start()
    wait_ready()

    win: dict[str, subprocess.Popen | None] = {"proc": None}

    def open_window(_=None) -> None:
        p = win["proc"]
        if p and p.poll() is None:
            return  # a window is already open
        win["proc"] = subprocess.Popen(_self_cmd("--window"))

    class DevanshApp(rumps.App):
        @rumps.clicked("Open Dashboard")
        def _open(self, _):
            open_window()

        @rumps.clicked("Open in Browser")
        def _browser(self, _):
            webbrowser.open(URL)

        @rumps.clicked("Launch at Login")
        def _login(self, sender):
            sender.state = not sender.state
            set_login(bool(sender.state))

        @rumps.clicked("Quit")
        def _quit(self, _):
            p = win["proc"]
            if p and p.poll() is None:
                p.terminate()
            rumps.quit_application()

    app = DevanshApp("Devansh OS", title="◐", quit_button=None)
    app.menu = ["Open Dashboard", "Open in Browser", None,
                "Launch at Login", None, "Quit"]
    app.menu["Launch at Login"].state = login_enabled()

    open_window()  # pop a window on first launch
    app.run()


def run_selftest() -> None:
    """Headless check: boot the embedded server and confirm it serves. Used to
    validate the packaged binary without launching any GUI."""
    import json
    threading.Thread(target=start_server, daemon=True).start()
    ok = wait_ready(30)
    providers = []
    try:
        data = json.load(urllib.request.urlopen(URL + "api/cards", timeout=5))
        providers = [c["provider"] for c in data["cards"]]
    except Exception:
        pass
    print(f"selftest: server_ready={ok} providers={providers}", flush=True)
    sys.exit(0 if ok and providers else 1)


def main() -> None:
    if "--selftest" in sys.argv:
        run_selftest()
    elif "--window" in sys.argv:
        run_window()
    else:
        run_menubar()


if __name__ == "__main__":
    main()
