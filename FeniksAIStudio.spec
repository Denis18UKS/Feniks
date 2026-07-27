# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)
datas = [(str(root / "web"), "web")]
bridge = root / "feniks" / "bin" / "Feniks.WindowsBridge.exe"
if bridge.exists():
    datas.append((str(bridge), "feniks/bin"))

a = Analysis(["app.py"], pathex=[str(root)], binaries=[], datas=datas, hiddenimports=["webview"],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="FeniksAIStudio", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=True, console=False,
          icon=[])
