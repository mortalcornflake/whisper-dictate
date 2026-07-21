# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Whisper Dictate macOS .app (onedir).

Build:  ./build-macos-app.sh   (or: python -m PyInstaller --noconfirm whisper_string.spec)

The app bundles its own Python interpreter + all macOS deps (rumps/pyobjc,
pynput, pyperclip, sounddevice+PortAudio, numpy, requests). External resources
stay external and env-driven: whisper.cpp binaries + the ~1.5GB model, the
recordings archive, and the log. The owner's .env is NEVER bundled (it holds the
API key); it's seeded into ~/Library/Application Support/WhisperDictate/ on first
launch — see app_paths.py.
"""

block_cipher = None

a = Analysis(
    ['dictate.py'],
    pathex=['.'],
    binaries=[],
    datas=[('.env.example', '.')],   # first-launch seed template (NO secrets)
    hiddenimports=[
        # Local modules (some are imported lazily — list explicitly so the
        # analyzer can't miss them).
        'app_paths', 'menubar_app', 'platform_io', 'platform_io.darwin',
        # rumps / Cocoa (menu-bar UI).
        'rumps',
        'AppKit', 'Cocoa', 'Foundation', 'objc', 'Quartz',
        'ApplicationServices', 'CoreText',
        # Audio + input + clipboard.
        'sounddevice', '_sounddevice',
        'pyperclip',
        'pynput', 'pynput.keyboard', 'pynput.keyboard._darwin',
        'pynput._util.darwin',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Windows-only / CUDA / not installed in the macOS venv. Suppresses
        # analysis warnings and shrinks the bundle. faster_whisper_backend itself
        # is safe to bundle (its heavy imports are lazy).
        'faster_whisper', 'ctranslate2', 'pynvml',
        'win11toast', 'pystray', 'PIL', 'Pillow', 'winsound', 'tray_app',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WhisperDictate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # UPX conflicts with macOS code signing
    console=False,        # menu-bar accessory: no Terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='WhisperDictate',
)

app = BUNDLE(
    coll,
    name='Whisper Dictate.app',
    bundle_identifier='com.mortalcornflake.whisper-dictate',
    info_plist={
        'CFBundleName': 'Whisper Dictate',
        'CFBundleDisplayName': 'Whisper Dictate',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1',
        'LSUIElement': True,          # menu-bar accessory: no Dock icon
        'LSMinimumSystemVersion': '10.13',
        'NSMicrophoneUsageDescription':
            'Whisper Dictate needs microphone access to transcribe your speech.',
        'NSAppleEventsUsageDescription':
            'Whisper Dictate pastes transcriptions by sending keystrokes through '
            'System Events.',
    },
)
