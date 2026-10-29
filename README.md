# 📚 會議資料庫

網址：https://chy23.github.io/meetinglib/ （公開，無需登入）

- `index.html`：網站，放在 GitHub Pages。
- `apps-script/Code.gs`：取出 PDF 文字（含 OCR）、每小時更新索引，並提供網站讀取的 API。

## 每週維護
把 PDF 丟進雲端資料夾，檔名格式：`YYYY-MM-DD_標題.pdf`。最慢 1 小時內出現在網站。

## 初次設定
1. 雲端建立資料夾、放入 PDF，複製網址 `folders/` 後的 ID。
2. script.google.com → 新增專案，貼上 `Code.gs`，填入 `FOLDER_ID`；左側「服務 ＋」加入 **Drive API**。
3. 執行 `setup` 並授權。
4. 部署 → 新增部署作業 → 網頁應用程式：執行身分「我」、存取權「所有人」。複製 `/exec` 結尾的網址。
5. 把網址貼到 `index.html` 的 `API_URL`。
6. GitHub repo → Settings → Pages → `main` 分支、`/ (root)`。
