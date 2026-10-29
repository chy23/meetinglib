/**
 * 會議資料庫 — Google Apps Script 索引程式
 * 負責把 PDF 文字取出，寫成資料夾內的 _index.json，供 GitHub Pages 網站讀取
 * 1. 把 FOLDER_ID 換成你的雲端資料夾 ID
 * 2. 在編輯器左側「服務」加入 Drive API (v3)
 * 3. 執行一次 setup()
 */
const FOLDER_ID = '請貼上資料夾ID';
const INDEX_NAME = '_index.json';
const NAME_RE = /^(\d{4}-\d{2}-\d{2})_(.+)\.pdf$/i;

/** 首次執行：建立索引 + 每小時自動檢查新檔 */
function setup() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('buildIndex').timeBased().everyHours(1).create();
  buildIndex();
}

/** 掃描資料夾，只對新增/修改過的 PDF 取出文字 */
function buildIndex() {
  const folder = DriveApp.getFolderById(FOLDER_ID);
  const old = {};
  const idx = findIndexFile_();
  if (idx) JSON.parse(idx.getBlob().getDataAsString('UTF-8')).forEach(m => (old[m.id] = m));

  const list = [];
  const it = folder.getFilesByType(MimeType.PDF);
  while (it.hasNext()) {
    const file = it.next();
    const m = file.getName().match(NAME_RE);
    if (!m) { console.warn('檔名不符規則，略過：' + file.getName()); continue; }
    const updated = file.getLastUpdated().toISOString();
    const prev = old[file.getId()];
    list.push({
      id: file.getId(),
      date: m[1],
      title: m[2],
      url: file.getUrl(),
      updated,
      text: prev && prev.updated === updated ? prev.text : extractText_(file),
    });
  }
  list.sort((a, b) => b.date.localeCompare(a.date));

  const json = JSON.stringify(list);
  if (idx) idx.setContent(json);
  else folder.createFile(INDEX_NAME, json, 'application/json');
}

/** 轉成 Google 文件（含 OCR，掃描檔也適用）後取文字，再刪除暫存檔 */
function extractText_(file) {
  const doc = Drive.Files.create(
    { name: '_ocr_tmp', mimeType: MimeType.GOOGLE_DOCS },
    file.getBlob(),
    { ocrLanguage: 'zh-TW' }
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
