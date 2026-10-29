# 📚 會議資料庫

網址：https://chy23.github.io/meetinglib/

- 網站（`index.html`）放在 GitHub Pages，使用者以 Google 帳號登入後，直接從 Google 雲端讀取資料。
- `apps-script/` 負責把 PDF 文字取出（含 OCR），每小時更新一次資料夾中的 `_index.json`。
- 權限 = 雲端資料夾的共用名單。

## 每週維護
把 PDF 丟進雲端資料夾，檔名格式：`YYYY-MM-DD_標題.pdf`（例如 `2026-10-15_週會記錄.pdf`）。

## 初次設定

### 1. 雲端資料夾
建立資料夾、放入 PDF，複製網址 `folders/` 後的 ID。

### 2. Apps Script（產生索引）
1. script.google.com → 新增專案，貼上 `apps-script/Code.gs`，填入 `FOLDER_ID`。
2. 左側「服務 ＋」加入 **Drive API**。
3. 執行 `setup` 並授權。完成後資料夾內會出現 `_index.json`。

### 3. Google Cloud OAuth 用戶端（讓網站能登入）
1. console.cloud.google.com → 建立專案 → 「API 和服務」→ 啟用 **Google Drive API**。
2. 「OAuth 同意畫面」：類型選「外部」，填應用程式名稱與信箱；在「測試使用者」加入所有可查看者的 Gmail（最多 100 人）。
3. 「憑證」→ 建立「OAuth 用戶端 ID」→ 類型「網頁應用程式」→ 已授權的 JavaScript 來源填 `https://chy23.github.io`。
4. 把用戶端 ID 與資料夾 ID 填入 `index.html` 上方的 `CLIENT_ID`、`FOLDER_ID`。

### 4. GitHub Pages
Repo → Settings → Pages → Source 選 `main` 分支、`/ (root)`。

### 5. 開放給某人
資料夾「共用」加入對方 Gmail（檢視者），並將其加到 OAuth「測試使用者」。
