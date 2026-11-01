#!/usr/bin/env bash
# 一鍵安裝「會議發布小秘書」至 macOS 應用程式目錄
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_SRC="${DIR}/MeetingPublisher.app"
DEST_APP="${HOME}/Applications/MeetingPublisher.app"

if [ ! -d "${APP_SRC}" ]; then
  echo "正在先執行編譯..."
  "${DIR}/build_app.sh"
fi

mkdir -p "${HOME}/Applications"
echo "📦 正在複製 MeetingPublisher.app 到 ${DEST_APP} ..."
rm -rf "${DEST_APP}"
cp -R "${APP_SRC}" "${DEST_APP}"

echo "🎉 安裝大成功！"
echo "您現在可以直接從 Spotlight（⌘ + 空白鍵搜尋 MeetingPublisher）開啟它。"
echo "若要立即啟動，請執行：open ~/Applications/MeetingPublisher.app"
