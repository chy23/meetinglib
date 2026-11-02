"""從 Apps Script 同步會議索引、PDF 與抽取實體圖檔（含表格截圖、照片）到 data/，並提煉重點摘要。"""
import base64, json, os, re, shutil, urllib.request

API = os.environ.get("API_URL") or open("index.html", encoding="utf-8").read().split("const API_URL = '")[1].split("'")[0]
ROOT = os.path.join(os.path.dirname(__file__), "..", "data")
PDF_DIR = os.path.join(ROOT, "pdf")
IMG_BASE_DIR = os.path.join(ROOT, "images")
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(IMG_BASE_DIR, exist_ok=True)

KNOWN_DEPTS = ["教務處", "學務處", "總務處", "輔導處", "人事室", "會計室", "幼兒園"]

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

def clean_url(u):
    return re.sub(r'[)）>，。；;]+$', '', u).strip()

def get_domain(u):
    m = re.search(r'https?://([^/]+)', u)
    return m.group(1).replace('www.', '') if m else ''

def get_icon(u, title):
    if 'forms.gle' in u or 'docs.google.com/forms' in u or '表單' in title:
        return '📝', '線上表單'
    if 'meet.google.com' in u or 'zoom' in u or '會議' in title:
        return '📹', '線上會議'
    if 'drive.google.com' in u or '雲端' in title:
        return '📁', '雲端資源'
    if 'youtube.com' in u or 'youtu.be' in u or '影音' in title:
        return '🎬', '影音說明'
    if 'padlet.com' in u:
        return '📌', '數位看板'
    if any(k in u for k in ['moocs', 'elearn', 'estudy']) or any(k in title for k in ['研習', '學習', '磨課師']):
        return '🎓', '研習學習網'
    return '🔗', '外部連結'

def extract_clean_links(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    links = []
    seen = set()

    for idx, l in enumerate(lines):
        raw_urls = re.findall(r'https?://[^\s)）>]+', l)
        for raw in raw_urls:
            url = clean_url(raw)
            if not url or url in seen or len(url) < 10 or '.' not in get_domain(url):
                continue
            seen.add(url)

            line_txt = l.replace(raw, '').strip()
            line_txt = re.sub(r'^[一二三四五六七八九十\d\.\(（\)]+、?\s*', '', line_txt)
            line_txt = re.sub(r'^[●✧★※◎\-]\s*', '', line_txt)
            line_txt = re.sub(r'[★※✧]+$', '', line_txt).strip()

            title = ''
            if len(line_txt) >= 4 and not line_txt.startswith('http') and not line_txt.startswith('）'):
                title = line_txt
            elif idx > 0:
                prev_line = lines[idx-1]
                prev_line = re.sub(r'^[一二三四五六七八九十\d\.\(（\)]+、?\s*', '', prev_line)
                prev_line = re.sub(r'^[●✧★※◎\-]\s*', '', prev_line)
                prev_line = re.sub(r'[★※✧]+$', '', prev_line).strip()
                if len(prev_line) >= 4 and not prev_line.startswith('http'):
                    title = prev_line

            if 'gifted.ntpc.edu.tw' in url:
                title = '新北資優鑑定系統報名'
            elif 'nias-school' in url:
                continue

            title = re.sub(r'^(表單連結|連結|網址)[：:]\s*', '', title)
            title = re.sub(r'^[）\)]\s*', '', title)
            title = re.sub(r'[：:]\s*$', '', title).strip()
            if not title:
                title = '相關參考連結'
            if len(title) > 60:
                title = title[:60] + '…'

            icon, cat = get_icon(url, title)
            domain = get_domain(url)
            links.append({
                'url': url,
                'title': title,
                'category': cat,
                'icon': icon,
                'domain': domain
            })
    return links

COMMON_SURNAMES = '陳林黃張李王吳劉蔡楊許鄭謝郭洪曾邱廖賴周徐蘇葉莊呂江何蕭羅高簡朱鍾施游彭詹胡顏柯翁魏孫樊范方鄧石戴宋薛'
SURNAME_GROUP = '[' + COMMON_SURNAMES + ']'

def sanitize_pii(text):
    """
    落實個人資料保護法、兒童及少年福利與權益保障法及學生輔導法：
    對會議記錄內可能間接識別特定受輔導、特教或個別學生的班級與姓名進行自動化去識別化脫敏保護
    """
    if not text:
        return ""
    
    # 遮罩班級+學生全名（排除學年度、處室、職稱等公務用語）
    def mask_name(m):
        cls = m.group(1)
        name = m.group(2)
        if any(term in name for term in ['學年', '年度', '試題', '考科', '校長', '主任', '公分', '元為', '教室', '分鐘', '期末', '期中', '複檢']):
            return m.group(0)
        if len(name) == 3:
            return f'{cls}{name[0]}○{name[2]}'
        elif len(name) == 2:
            return f'{cls}{name[0]}○'
        return m.group(0)

    # 1. 班級 + 姓氏 + 生 (如 101 張生 -> 101 ○生)
    text = re.sub(rf'([1-6]\d{{2}}\s*)({SURNAME_GROUP})生', r'\1○生', text)
    # 2. 班級 + 常見姓氏全名 2-3 字 (如 508陳榮佑 -> 508陳○佑)
    text = re.sub(rf'([1-6]\d{{2}}\s*)({SURNAME_GROUP}[\u4e00-\u9fa5]{{1,2}})(?=\s|$)', mask_name, text)
    return text

def parse_meeting_filename(filename_or_title):
    """
    智慧解析檔名或標題中的乾淨會議名稱與版本號：
    支援：
      '2026-09-02_擴大行政會議 (4 版).pdf' -> title='擴大行政會議', version='4版'
      '2026-09-30_擴大行政會議 (2 版)-.pdf' -> title='擴大行政會議', version='2版'
      '2026-10-25_擴大行政會議 (1版).pdf' -> title='擴大行政會議', version='1版'
      '擴大行政會議 (4 版)' -> title='擴大行政會議', version='4版'
    """
    raw = filename_or_title.strip()
    raw = re.sub(r'\.pdf$', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'[\s\-_\–\~]+$', '', raw)
    
    # 移除開頭的日期 (若有)
    raw = re.sub(r'^\d{4}-\d{2}-\d{2}_', '', raw)
    
    # 比對版本號：如 (4 版)、(2 版)-、(1版)、（第3版）、(v2)
    ver_match = re.search(r'[\(（\[\s_]+(?:第\s*)?(\d+|[vV]\d+)\s*版?[\)）\]\s_\-]*$', raw)
    if not ver_match:
        ver_match = re.search(r'[\(（\[](.+?版)[\)）\]]', raw)
        
    version = ""
    clean_title = raw
    if ver_match:
        ver_text = ver_match.group(0).strip()
        num_m = re.search(r'(\d+)', ver_text)
        if num_m:
            version = f"{num_m.group(1)}版"
        else:
            version = re.sub(r'[\(\)（）\[\]\s\-]', '', ver_text)
        clean_title = raw[:ver_match.start()].strip()
        clean_title = re.sub(r'[\s\-_\(（]+$', '', clean_title)
        
    return clean_title, version

def enrich_meeting(m):
    """提取學年度、週次、處室標籤、版本號與提煉本次會議各項連結"""
    # 智慧分離標題與版本號（如 擴大行政會議 (4 版) -> 擴大行政會議 + 4版）
    raw_title = m.get("title", "")
    clean_title, version = parse_meeting_filename(raw_title)
    m["title"] = clean_title
    if version:
        m["version"] = version

    text = sanitize_pii(m.get("text", ""))
    m["text"] = text
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    # 處室標籤（僅當該處室確有獨立報告標題時才納入標籤，避免隨意提及誤判）
    tags = []
    for dept in KNOWN_DEPTS:
        pattern = r'【\s*' + re.escape(dept) + r'\s*】|' + re.escape(dept) + r'報告'
        if dept == '總務處':
            pattern += r'|【出納組】|【事務組】|【文書組】'
        if re.search(pattern, text):
            tags.append(dept)
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

    # 會議分類（校務會議、備課會議、教師午會等）
    title = m.get("title", "")
    category = "教師午會"
    if "校務會議" in title:
        category = "校務會議"
    elif "備課" in title:
        category = "備課會議"
    elif "行政會議" in title:
        category = "行政會議"
    elif "學年會議" in title:
        category = "學年會議"
    elif "課發會" in title or "課程發展" in title:
        category = "課程發展委員會"
    elif "特推會" in title or "特殊教育" in title:
        category = "特推會"
    elif "導師會議" in title:
        category = "導師會議"
    else:
        category = re.sub(r'(會議)?(紀錄|記錄)$', '', title).strip() or title or "其他會議"

    m["academic_year"] = academic_year
    m["week"] = week_str
    m["category"] = category
    m["tags"] = tags
    m["links"] = extract_clean_links(text)
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
