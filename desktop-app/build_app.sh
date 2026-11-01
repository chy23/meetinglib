#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="MeetingPublisher"
APP_DIR="${DIR}/${APP_NAME}.app"
CONTENTS_DIR="${APP_DIR}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"

echo "🔨 [1/4] 清理並建立 macOS 應用程式結構..."
rm -rf "${APP_DIR}"
mkdir -p "${MACOS_DIR}"
mkdir -p "${RESOURCES_DIR}"

echo "🚀 [2/4] 編譯 Swift 原生 Menu Bar 應用程式..."
swiftc "${DIR}/main.swift" \
  -O \
  -framework Cocoa \
  -framework PDFKit \
  -framework UserNotifications \
  -o "${MACOS_DIR}/${APP_NAME}"

echo "📋 [3/4] 產生 Info.plist 配置檔與圖示..."
cat << 'EOF' > "${CONTENTS_DIR}/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>MeetingPublisher</string>
    <key>CFBundleIdentifier</key>
    <string>org.liyuan.meetingpublisher</string>
    <key>CFBundleName</key>
    <string>會議資料庫發布小秘書</string>
    <key>CFBundleDisplayName</key>
    <string>會議發布小秘書</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# 製作 AppIcon.icns
SRC_ICON="${DIR}/../apple-touch-icon.png"
if [ -f "${SRC_ICON}" ]; then
  ICONSET="/tmp/MeetingPublisher.iconset"
  rm -rf "${ICONSET}"
  mkdir -p "${ICONSET}"
  for s in 16 32 64 128 256 512; do
    sips -z ${s} ${s} "${SRC_ICON}" --out "${ICONSET}/icon_${s}x${s}.png" >/dev/null 2>&1
    if [ ${s} -le 256 ]; then
      s2=$((s * 2))
      sips -z ${s2} ${s2} "${SRC_ICON}" --out "${ICONSET}/icon_${s}x${s}@2x.png" >/dev/null 2>&1
    fi
  done
  iconutil -c icns "${ICONSET}" -o "${RESOURCES_DIR}/AppIcon.icns" >/dev/null 2>&1
  rm -rf "${ICONSET}"
fi

echo "🎨 [4/4] 複製資源與輔助腳本..."
# 確保 publisher_engine.py 具備執行權限
chmod +x "${DIR}/publisher_engine.py"

echo "✅ 編譯打包完成！"
echo "應用程式位置: ${APP_DIR}"
echo "可直接在 Finder 雙擊執行，或執行以下指令安裝至應用程式目錄："
echo "cp -r \"${APP_DIR}\" /Applications/"
