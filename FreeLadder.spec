# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:\\freevpn\\FreeLadder\\freeladder\\app_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('E:\\freevpn\\FreeLadder\\config.example.yaml', '.')],
    hiddenimports=['uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'playwright', 'playwright.async_api', 'customtkinter', 'freeladder', 'freeladder.core', 'freeladder.scraper', 'freeladder.tester', 'freeladder.exporter', 'freeladder.gui', 'freeladder.web', 'freeladder.cli', 'freeladder.browser'],
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
    [],
    exclude_binaries=True,
    name='FreeLadder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FreeLadder',
)
