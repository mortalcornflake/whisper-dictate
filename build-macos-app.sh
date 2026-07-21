#!/bin/bash
# Build the standalone macOS .app for Whisper Dictate (PyInstaller onedir),
# ad-hoc sign it, and print next steps. See MACOS_APP_BUILD.md for the design.
#
# Output: dist/Whisper Dictate.app
set -euo pipefail

cd "$(dirname "$0")"
source venv/bin/activate

if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip install --quiet "pyinstaller>=6.0"
fi

echo "Building .app (onedir) — first build can take a couple minutes..."
python -m PyInstaller --noconfirm whisper_string.spec

APP="dist/Whisper Dictate.app"
if [ ! -d "$APP" ]; then
    echo "❌ Build failed: $APP not created"
    exit 1
fi

echo "Ad-hoc code signing..."
codesign --deep --force --sign - "$APP" 2>/dev/null || \
    echo "⚠️  codesign failed (continue anyway — the app may still run unsigned locally)."

echo
echo "✅ Built and signed: $APP"
echo
echo "Next steps:"
echo "  1. Install:    cp -R \"$APP\" /Applications/"
echo "  2. Launch:     open \"/Applications/Whisper Dictate.app\""
echo "  3. Grant in System Settings → Privacy & Security:"
echo "       • Input Monitoring  (hotkey)"
echo "       • Accessibility     (paste)"
echo "       • Microphone        (recording)"
echo "       • Automation        (System Events paste) — if prompted"
echo "  4. On first launch, config migrates to:"
echo "       ~/Library/Application Support/WhisperDictate/.env"
