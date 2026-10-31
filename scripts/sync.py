"""從 Apps Script 同步會議索引、PDF 與抽取實體圖檔（含表格截圖、照片）到 data/，並提煉重點摘要。"""
import base64, json, os, re, shutil, urllib.request

API = os.environ.get("API_URL") or open("index.html", encoding="utf-8").read().split("const API_URL = '")[1].split("'")[0]
ROOT = os.path.join(os.path.dirname(__file__), "..", "data")
PDF_DIR = os.path.join(ROOT, "pdf")
IMG_BASE_DIR = os.path.join(ROOT, "images")
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(IMG_BASE_DIR, exist_ok=True)

KNOWN_DEPTS = ["教務處", "學務處", "總務處", "輔導處", "輔導室", "人事室", "會計室", "幼兒園"]

def get(url):
    with urllib.request.urlopen(url, timeout=300) as r:
        return r.read()

def extract_pdf_images(pdf_path, dest_dir):
    """從 PDF 中自動抽出嵌入的實體 JPEG 圖片（含表格截圖、活動照片、公文宣導圖）"""
    os.makedirs(dest_dir, exist_ok=True)
    with open(pdf_path, "rb") as f:
        content = f.read()
    
    matches = re.finditer(rb'/Subtype\s*/Image[\s\S]*?/Filter\s*/DCTDecode[\s\S]*?stream\r?\n([\s\S]*?)\r?\nendstream', content)
    images = []
    idx = 0
    for m in matches:
        raw = m.group(1)
        if raw.startswith(b'\xff\xd8') and len(raw) >= 8000:
            idx += 1
            filename = f"img_{idx}.jpg"
            dest_path = os.path.join(dest_dir, filename)
            with open(dest_path, "wb") as img_f:
                img_f.write(raw)
            images.append(filename)
    return images

def enrich_meeting(m):
    """提取學年度、週次、處室標籤與條列式核心摘要"""
    text = m.get("text", "")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    # 處室標籤
    tags = []
    for dept in KNOWN_DEPTS:
        if dept in text:
            tags.append(dept.replace("輔導處", "輔導室"))
    tags = list(dict.fromkeys(tags))
    
    # 學年度與週次
    academic_year = ""
    week_str = ""
    for l in lines[:5]:
        m_ay = re.search(r'(\d{3})\s*學年度\s*(第[一二]學期)?', l)
        if m_ay:
            academic_year = f"{m_ay.group(1)}學年度 {m_ay.group(2) or ''}".strip()
        m_wk = re.search(r'第([一二三四五六七八九十\d]+)週', l)
        if m_wk:
            week_str = f"第{m_wk.group(1)}週"
            
    if not academic_year and m.get("date"):
        y, mo = int(m["date"][:4]), int(m["date"][5:7])
        roc_y = y - 1911
        sem = "第一學期" if mo >= 8 or mo == 1 else "第二學期"
        ay = roc_y if mo >= 8 else roc_y - 1
        academic_year = f"{ay}學年度 {sem}"

    # 抽取重點
    summary_items = []
    in_chair = False
    in_dept = False
    current_dept = None
    
    for l in lines:
        if re.search(r'[伍肆參]、\s*(?:主席|校長)報告', l):
            in_chair = True
            in_dept = False
            continue
        elif re.search(r'[陸伍柒]、\s*處室報告', l):
            in_chair = False
            in_dept = True
            continue
        elif re.search(r'[柒陸捌]、\s*(?:討論事項|臨時動議|散會)', l):
            in_chair = False
            in_dept = False
            continue
            
        if in_chair and re.match(r'^[一二三四五六七八九十]、', l):
            clean = re.sub(r'^[一二三四五六七八九十]、\s*', '', l)
            if len(clean) > 6:
                summary_items.append({"category": "校長/主席", "text": clean[:85]})
        elif in_dept:
            for dept in KNOWN_DEPTS:
                if f"【{dept}】" in l or f"{dept}報告" in l:
                    current_dept = dept.replace("輔導處", "輔導室")
            if current_dept and re.match(r'^[一二三四五六七八九十]、', l):
                clean = re.sub(r'^[一二三四五六七八九十]、\s*', '', l)
                if len(clean) > 6 and not any(s["category"] == current_dept and len(s["text"]) > 0 for s in summary_items if s["category"] == current_dept):
                    summary_items.append({"category": current_dept, "text": clean[:85]})

    m["academic_year"] = academic_year
    m["week"] = week_str
    m["tags"] = tags
    m["summary"] = summary_items[:6]
    return m

def optimize_pdf(pdf_path):
    """若有 pypdf 則壓縮重整 PDF 體積"""
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)
        tmp = pdf_path + ".tmp"
        with open(tmp, "wb") as f:
            writer.write(f)
        if os.path.getsize(tmp) < os.path.getsize(pdf_path):
            os.replace(tmp, pdf_path)
        else:
            os.remove(tmp)
    except Exception:
        pass

def main():
    print("開始從 Apps Script 獲取最新資料...")
    raw = get(API)
    new = json.loads(raw)
    idx_path = os.path.join(ROOT, "index.json")
    old = {m["id"]: m for m in json.load(open(idx_path, encoding="utf-8"))} if os.path.exists(idx_path) else {}

    enriched_list = []
    for m in new:
        path = os.path.join(PDF_DIR, m["id"] + ".pdf")
        if not (os.path.exists(path) and old.get(m["id"], {}).get("updated") == m["updated"]):
            print("下載 PDF:", m["date"], m["title"])
            b64 = get(f"{API}?pdf={m['id']}").decode()
            if b64.startswith("ERR"):
                raise SystemExit(b64)
            open(path, "wb").write(base64.b64decode(b64))
            optimize_pdf(path)

        enriched = enrich_meeting(m)
        
        # 抽取實體圖片檔
        dest_dir = os.path.join(IMG_BASE_DIR, m["id"])
        imgs = extract_pdf_images(path, dest_dir)
        enriched["images"] = [f"data/images/{m['id']}/{f}" for f in imgs]
        
        enriched_list.append(enriched)

    keep = {m["id"] + ".pdf" for m in new}
    for f in os.listdir(PDF_DIR):
        if f not in keep:
            print("移除舊檔:", f)
            os.remove(os.path.join(PDF_DIR, f))

    keep_dirs = {m["id"] for m in new}
    if os.path.exists(IMG_BASE_DIR):
        for d in os.listdir(IMG_BASE_DIR):
            if d not in keep_dirs:
                shutil.rmtree(os.path.join(IMG_BASE_DIR, d), ignore_errors=True)

    json.dump(enriched_list, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("同步、圖片抽取與結構化分析完成，共", len(enriched_list), "份會議")

if __name__ == "__main__":
    main()
