# PyInstaller spec — builds "Devansh OS.app" (macOS menu-bar app + window).
# Build:  pyinstaller --noconfirm packaging/DevanshOS.spec   (from repo root)
import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # repo root

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("apscheduler")
    + [
        # providers are imported via app.providers but list them to be safe
        "app.providers.github", "app.providers.leetcode", "app.providers.gym",
        "app.providers.sleep", "app.providers.chemvecto", "app.providers.claude",
        "app.providers.manual",
    ]
)

datas = [
    (os.path.join(ROOT, "web"), "web"),
    (os.path.join(ROOT, "migrations"), "migrations"),
    (os.path.join(ROOT, ".env.example"), "."),
]

a = Analysis(
    [os.path.join(ROOT, "desktop.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Devansh OS",
    console=False,          # GUI app, no terminal window
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Devansh OS")

app = BUNDLE(
    coll,
    name="Devansh OS.app",
    icon=None,
    bundle_identifier="com.devansh.os",
    info_plist={
        # Menu-bar agent: no Dock icon, lives in the status bar.
        "LSUIElement": True,
        "CFBundleName": "Devansh OS",
        "NSHighResolutionCapable": True,
    },
)
