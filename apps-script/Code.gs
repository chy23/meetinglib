/**
 * 會議資料庫 — Google Apps Script 索引程式
 * 負責把 PDF 文字取出，寫成資料夾內的 _index.json，供 GitHub Pages 網站讀取
 * 1. 把 FOLDER_ID 換成你的雲端資料夾 ID
 * 2. 在編輯器左側「服務」加入 Drive API (v3)
 * 3. 執行一次 setup()
 * 4. 部署 → 網頁應用程式（執行身分：我；存取權：所有人），把 /exec 網址貼到 index.html
 */
const FOLDER_ID = '請貼上資料夾ID';
const INDEX_NAME = '_index.json';
const NAME_RE = /^(\d{4}-\d{2}-\d{2})_(.+)\.pdf$/i;

/** 網站讀取資料的 API（公開） */
function doGet() {
  const f = findIndexFile_();
  return ContentService.createTextOutput(f ? f.getBlob().getDataAsString('UTF-8') : '[]')
    .setMimeType(ContentService.MimeType.JSON);
}

/** 首次執行：建立索引 + 每小時自動檢查新檔 */
function setup() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('buildIndex').timeBased().everyHours(1).create();
  buildIndex();
}

/** 掃描資料夾，只對新增/修改過的 PDF 取出文字（每處理完一份就存檔，超過 5 分鐘先停，下次排程接著做） */
function buildIndex() {
  const start = Date.now();
  const folder = DriveApp.getFolderById(FOLDER_ID);
  const old = {};
  const idx = findIndexFile_();
  if (idx) JSON.parse(idx.getBlob().getDataAsString('UTF-8')).forEach(m => (old[m.id] = m));

  const list = [];
  const pending = [];
  const it = folder.getFilesByType(MimeType.PDF);
  while (it.hasNext()) {
    const file = it.next();
    const m = file.getName().match(NAME_RE);
    if (!m) { console.warn('檔名不符規則，略過：' + file.getName()); continue; }
    const updated = file.getLastUpdated().toISOString();
    const prev = old[file.getId()];
    const item = { id: file.getId(), date: m[1], title: m[2], url: file.getUrl(), updated: prev ? prev.updated : '', text: prev ? prev.text : '' };
    list.push(item);
    if (!prev || prev.updated !== updated) pending.push({ item, file });
  }

  for (const { item, file } of pending) {
    if (Date.now() - start > 5 * 60 * 1000) { console.log('時間將到，剩餘檔案下次處理'); break; }
    try {
      file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW); // 讓「查看原始 PDF」人人可開
    } catch (e) { console.warn('無法設定共用：' + e.message); }
    try {
      item.text = extractText_(file);
      console.log('完成：' + file.getName());
    } catch (e) {
      item.text = '（此份文字擷取失敗，請點「查看原始 PDF」閱讀）';
      console.warn('擷取失敗：' + file.getName() + ' → ' + e.message);
    }
    item.updated = file.getLastUpdated().toISOString();
    save_(folder, list);
  }
  save_(folder, list);
}

function save_(folder, list) {
  const done = list.slice().sort((a, b) => b.date.localeCompare(a.date));
  const json = JSON.stringify(done);
  const idx = findIndexFile_();
  if (idx) idx.setContent(json);
  else folder.createFile(INDEX_NAME, json, 'application/json');
}

/** 轉成 Google 文件（含 OCR，掃描檔也適用）後取文字，再刪除暫存檔 */
function extractText_(file) {
  const doc = Drive.Files.create(
    { name: '_ocr_tmp', mimeType: 'application/vnd.google-apps.document' },
    file.getBlob()
  );
  try {
    return DocumentApp.openById(doc.id).getBody().getText();
  } finally {
    DriveApp.getFileById(doc.id).setTrashed(true);
  }
}

function findIndexFile_() {
  const it = DriveApp.getFolderById(FOLDER_ID).getFilesByName(INDEX_NAME);
  return it.hasNext() ? it.next() : null;
}
