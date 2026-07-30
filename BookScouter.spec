# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Konfiguration für die BookScouter.exe.

Neu bauen (legt die .exe direkt im Projektordner ab):

    pyinstaller BookScouter.spec --distpath . --workpath build --noconfirm

Anmerkungen:
- `collect_all('customtkinter')` ist nötig, weil customtkinter seine Themes
  als JSON-Dateien nachlädt; ohne sie startet die gepackte App nicht.
- `pathex=['.')` sorgt dafür, dass `bookscouter/ui.py` seine Geschwister-
  Module über `from bookscouter...` findet.
- `console=False`: die App ist ein Fenster, kein Terminal. Deshalb ruft
  `scrapers/base.py` curl mit CREATE_NO_WINDOW auf, sonst blitzte bei jeder
  Abfrage eine Konsole auf.
- Das Icon liegt als `assets/BookScouter.ico` bei und wird zusätzlich ins
  Bündel kopiert, weil die App es zur Laufzeit auch als Fenstersymbol setzt.
  Neu erzeugen lässt es sich mit `python assets/make_icon.py`.
"""

from PyInstaller.utils.hooks import collect_all

datas = [('assets/BookScouter.ico', 'assets')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['bookscouter\\ui.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BookScouter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/BookScouter.ico'],
)
