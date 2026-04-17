# -*- mode: python ; coding: utf-8 -*-

app_plist = {
    "CFBundleDocumentTypes": [
        {
            "CFBundleTypeName": "JSON",
            "CFBundleTypeExtensions": ["json"],
            "CFBundleTypeRole": "Viewer",
        }
    ]
}

a = Analysis(
    ['analyze_events.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('state_analysis_tool/schema/schema_reference.txt', 'state_analysis_tool/schema'),
    ],
    hiddenimports=[],
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
    name='GameStateAnalysis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='GameStateAnalysis.app',
    info_plist=app_plist,
)
