# 📚 會議資料庫發布小秘書 (MeetingPublisher for macOS)

專為麗園國小會議資料庫打造的 macOS 原生選單列狀態列小工具（Menu Bar App），實現 **「將 PDF 檔案拖入，一鍵雙向同步至 Google 雲端硬碟與 GitHub Pages 網站發布」**！

---

## ✨ 核心特色
1. **零等待輕量原生**：以 Apple Swift 6.4 + Cocoa + PDFKit 原生打造，體積僅約 270 KB，記憶體佔用極低，點擊瞬間啟動。
2. **常駐 macOS 狀態列 (Menu Bar)**：平日隱身於右上角狀態列（圖示：`📚`），絕不佔用 Dock 圖示空間。
3. **直覺拖曳發布 (Drag & Drop)**：
   - 支援將會議 PDF 直接拖曳進懸浮面板。
   - 智慧檔名辨識：自動從 `YYYY-MM-DD_會議名稱.pdf` 解析出日期與名稱。
4. **雙平台推播發布**：
   - **第一平台：Google 雲端硬碟**：自動同步存檔至本機 Google 雲端硬碟 (`/Users/chiahua/Google 雲端硬碟/會議資料庫`)，Google Drive 自動背景上傳。
   - **第二平台：GitHub Pages 網站**：以 Apple PDFKit 原生抽取全文與圖片，自動執行學生個資脫敏（PII Sanitization），更新 `index.json` 並推送到 GitHub，30 秒內網站即時上線。
5. **macOS 原生系統推播通知**：發布或同步完成時，macOS 右上角即時跳出橫幅提醒。

---

## 🚀 快速啟動
- **直接開啟**：
  ```bash
  open ~/Applications/MeetingPublisher.app
  ```
- **重新編譯**：
  ```bash
  cd desktop-app && ./build_app.sh
  ```

---

## 🪟 未來擴展至 Windows 規劃
本架構之發布核心已模組化拆分為 `publisher_engine.py`，未來擴展至 Windows 時：
- 可使用 Python `pystray` + `Tkinter/CustomTkinter` 或 C# / WPF 打造 Windows 系統匣（System Tray）圖示小工具。
- 發布邏輯無縫共用同一套 `publisher_engine.py`，即可在 Windows 達成一模一樣的拖曳與雙站部署體驗。
