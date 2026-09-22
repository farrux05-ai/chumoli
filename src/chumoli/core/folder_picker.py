"""
Native OS folder picker for local desktop use (chumoli ui on the same machine).

Browser cannot expose real absolute paths for security reasons, so the API
process opens a system dialog and returns the chosen path to the UI.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def pick_folder(title: str = "Eksport papkasini tanlang") -> str | None:
    """Open a native directory dialog. Returns absolute path or None if cancelled.

    Tries, in order:
      1. tkinter filedialog (works when DISPLAY / GUI available)
      2. zenity (GNOME)
      3. kdialog (KDE)
    """
    path = _pick_tkinter(title)
    if path is not None:
        return path
    path = _pick_zenity(title)
    if path is not None:
        return path
    path = _pick_kdialog(title)
    if path is not None:
        return path
    raise RuntimeError(
        "Papka tanlash oynasi ochilmadi. DISPLAY yo'q yoki tkinter/zenity "
        "o'rnatilmagan. Path ni qo'lda yozing yoki bo'sh qoldiring "
        "(standart: ~/chumoli-data/exports/<pipeline>/)."
    )


def _normalize(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    return str(Path(s).expanduser().resolve())


def _pick_tkinter(title: str) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None
    if not os.environ.get("DISPLAY") and os.name != "nt":
        # Headless Linux/mac without display — skip (mac may still work)
        if sys_platform_linux():
            return None
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        chosen = filedialog.askdirectory(title=title, mustexist=True)
        root.destroy()
        return _normalize(chosen if isinstance(chosen, str) else None)
    except Exception:
        return None


def sys_platform_linux() -> bool:
    return sys.platform.startswith("linux")


def _pick_zenity(title: str) -> str | None:
    if not shutil.which("zenity"):
        return None
    try:
        r = subprocess.run(
            [
                "zenity",
                "--file-selection",
                "--directory",
                f"--title={title}",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if r.returncode != 0:
            return None
        return _normalize(r.stdout)
    except Exception:
        return None


def _pick_kdialog(title: str) -> str | None:
    if not shutil.which("kdialog"):
        return None
    try:
        r = subprocess.run(
            ["kdialog", "--getexistingdirectory", str(Path.home()), "--title", title],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if r.returncode != 0:
            return None
        return _normalize(r.stdout)
    except Exception:
        return None
