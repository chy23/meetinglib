"""從 Apps Script 同步會議索引、PDF 與抽取實體圖檔（含表格截圖、照片）到 data/，並提煉重點摘要。"""
import base64, json, os, re, shutil, urllib.request

API = os.environ.get("API_URL") or open("index.html", encoding="utf-8").read().split("const API_URL = '")[1].split("'")[0]
ROOT = os.path.join(os.path.dirname(__file__), "..", "data")
PDF_DIR = os.path.join(ROOT, "pdf")
IMG_BASE_DIR = os.path.join(ROOT, "images")
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(IMG_BASE_DIR, exist_ok=True)

KNOWN_DEPTS = ["教務處", "學務處", "總務處", "輔導處", "人事室", "會計室", "幼兒園"]

# 百家姓與常見姓氏
SURNAMES = set('陳林黃張李王吳劉蔡楊許鄭謝洪郭邱曾廖賴徐周葉蘇莊江呂何羅高蕭潘朱簡彭游詹胡施沈余盧梁趙顏柯翁魏孫樊丁戴範宋鄧杜傅侯曹薛馬董溫唐藍石鍾白古汪卓湯馮方童常嚴尤邵韓歐甘阮涂蒲鄒秦黎盛鮑熊康駱毛狄戚齊崔雷全尹屈凌賀倪管項葛于時樂元卜顧孟平黃和穆湛禹成舒祝董席季麻強賈路婁梅夏田霍萬莫房裘單杭包諸左吉邢陸榮荀羊段富烏焦巴車班仰秋仲伊宮寧仇武符景龍幸祖司韶黎薄白蒲賴藺蒙池喬聞譚貢姬扶冉宰通邊扈燕農柴充容向古易國文廣敖融冷辛關權')

# 既有已驗證之麗園國小教職員名冊種子
BASE_STAFF_NAMES = {
    '丁常皓', '何冠宏', '余亭薇', '余思頻', '余道規', '卓芙如', '吳展昀', '吳翠娥', 
    '周瑩喬', '唐玉蟬', '唐鶯倫', '孫筱茜', '宋嘉桂', '宋怡瑩', '廖建超', '廖若雯', 
    '張巧玉', '張豐琪', '張靖妤', '彭慧怡', '施杰翰', '朱容樂', '李惠心', '李萬鈞', 
    '李貴評', '林宥嫻', '林惠敏', '林憲宏', '林欣樺', '林淑如', '林阿春', '林姿君', 
    '柯宜均', '楊家驊', '段生莉', '洪春秀', '洪浩菱', '洪諾帆', '王家宜', '王秀婷', 
    '王秀末', '胡博鈞', '胡筱瑄', '莊展榮', '蔡欣倫', '蔡欣家', '蔡萊拉', '蕭人龍', 
    '蘇姵菁', '蘇愛智', '蘇琦雅', '許碧玲', '謝驊', '賴韻晴', '邱郁芳', '邱駖珍', 
    '郭品萱', '郭秋汶', '鄧馨鍬', '鍾依穎', '陳威霖', '陳宜平', '陳建宏', '陳淑芬', 
    '陳福德', '陳羿臻', '陳英叡', '陳韋儒', '陳榮佑', '韓淇', '高敏翠', '高漢懋', 
    '黃國政', '黃巧雲', '黃曉梅', '黃榮富', '黃淑娟', '黃玉芬', '黃玉葉', '黃瑜萱', 
    '黃祖順', '黃筑翊', '詹景文', '范繡麗', '羅淑娟', '章慧媛'
}

STAFF_STOPWORDS = {
    '一年級', '二年級', '三年級', '四年級', '五年級', '六年級', '幼兒園', '全體', '全校',
    '學校', '各位', '導師', '各班', '本校', '學生', '家長', '科任', '審稿', '撰稿',
    '體育', '衛生', '輔導', '學務', '教務', '總務', '人事', '會計', '出納', '事務',
    '文書', '資訊', '設備', '教學', '註冊', '生教', '訓育', '特教', '幼兒', '活動',
    '謝謝', '感謝', '麻煩', '歡迎', '敬請', '拜託', '提醒', '證明', '說明', '完成',
    '參考', '登記', '申請', '繳交', '收取', '很多', '少數', '處理', '評選', '展示',
    '成果', '協助', '支援', '搬運', '整理', '時間', '地點', '主席', '記錄', '開會',
    '視聽', '博愛', '麗園', '麗正', '線上', '傳閱', '研習', '工作', '方案', '代課'
}

def mask_name(name):
    """將姓名中間字進行去識別化遮蔽（如：施杰翰 -> 施○翰、謝驊 -> 謝○）"""
    if len(name) == 3:
        return name[0] + '○' + name[2]
    elif len(name) == 2:
        return name[0] + '○'
    elif len(name) >= 4:
        return name[:-2] + '○' + name[-1]
    return name

def discover_staff_names(meeting_list):
    """動態掃描會議記錄，辨識新出現的教職員姓名，並與基礎名冊合併"""
    names = set(BASE_STAFF_NAMES)
    title_regex = r'(?:校\s*長|主\s*任|組\s*長|老\s*師|教\s*練|幹\s*事|執\s*秘|專輔教師|學年主任|心理師|社工師|護理師|醫\s*師)'

    for m in meeting_list:
        txt = m.get('text', '')
        # 1. 職稱前姓名
        for match in re.finditer(rf'(?<![感謝謝謝多謝\w])([\u4e00-\u9fa5]{{2,3}})\s*(?:{title_regex}|師\b)', txt):
            n = match.group(1).strip()
            for prefix in ['班', '級', '處', '室', '隊', '組', '會', '任', '表', '的', '及', '由', '與', '請']:
                if n.startswith(prefix):
                    n = n[1:]
            if 2 <= len(n) <= 3 and n[0] in SURNAMES and n not in STAFF_STOPWORDS:
                if not any(sw in n for sw in ['級', '校', '年', '各', '本', '感', '謝', '師', '處', '室', '會']):
                    names.add(n)

        # 2. 出席人員名單
        for m_att in re.finditer(r'出席[人員者]*[：:]([\s\S]*?)(?:\n\s*伍|\n\s*陸|\n\s*肆|\n\s*參|\n\s*貳|\n\s*壹|\n\n)', txt):
            chunk = m_att.group(1)
            chunk = re.sub(rf'{title_regex}|師|代表|家長|學生|委員|專輔教師|學年主任|代理|記錄', ' ', chunk)
            chunk = re.sub(r'[一二三四五六七八九十\d]+年級|(教務處|學務處|總務處|輔導處|資源班|幼兒園)', ' ', chunk)
            for token in re.split(r'[,、，\s\n]+', chunk):
                token = token.strip()
                if 2 <= len(token) <= 3 and token[0] in SURNAMES and token not in STAFF_STOPWORDS:
                    if not any(sw in token for sw in ['級', '校', '年', '各', '本', '感', '謝', '師', '處', '室', '會']):
                        names.add(token)

        # 3. 主席與記錄
        for m_pr in re.finditer(r'(?:主席|記錄)[：:\s]+([\u4e00-\u9fa5]{2,3})', txt):
            n = m_pr.group(1).strip()
            if 2 <= len(n) <= 3 and n[0] in SURNAMES and n not in STAFF_STOPWORDS:
                names.add(n)

    return sorted(names, key=lambda x: -len(x))

def anonymize_pdf(pdf_path, names):
    """使用 PyMuPDF 在 PDF 實體中抹除教職員姓名中間字，並繪製標準 ○ 圓圈"""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        modified = False
        for pno in range(len(doc)):
            page = doc[pno]
            circles = []
            for name in names:
                rects = page.search_for(name)
                for r in rects:
                    w = r.x1 - r.x0
                    if len(name) == 3:
                        mid_r = fitz.Rect(r.x0 + w * 0.28, r.y0 - 0.5, r.x0 + w * 0.72, r.y1 + 0.5)
                    else:
                        mid_r = fitz.Rect(r.x0 + w * 0.48, r.y0 - 0.5, r.x1, r.y1 + 0.5)
                    page.add_redact_annot(mid_r, fill=(1, 1, 1))
                    center = fitz.Point((mid_r.x0 + mid_r.x1) / 2, (mid_r.y0 + mid_r.y1) / 2)
                    radius = min(mid_r.width, mid_r.height) * 0.38
                    circles.append((center, radius))
                    modified = True
            if circles:
                page.apply_redactions()
                for c, rad in circles:
                    page.draw_circle(c, rad, color=(0.25, 0.25, 0.25), fill=(1, 1, 1), width=1.1)

        if modified:
            tmp = pdf_path + ".tmp"
            doc.save(tmp, garbage=4, deflate=True)
            doc.close()
            os.replace(tmp, pdf_path)
            print(f"已完成 PDF 姓名去識別化：{os.path.basename(pdf_path)}")
        else:
            doc.close()
    except Exception as e:
        print(f"PDF 去識別化略過或異常：{e}")

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

def enrich_meeting(m):
    """提取學年度、週次、處室標籤與提煉本次會議各項連結"""
    text = m.get("text", "")
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

    m["academic_year"] = academic_year
    m["week"] = week_str
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

    # 自動辨識全校教職員名單（含基礎種子名冊與動態辨識）
    all_staff_names = discover_staff_names(new)
    print(f"辨識出 {len(all_staff_names)} 位教職員姓名，準備執行自動去識別化...")

    enriched_list = []
    for m in new:
        path = os.path.join(PDF_DIR, m["id"] + ".pdf")
        downloaded = False
        if not (os.path.exists(path) and old.get(m["id"], {}).get("updated") == m["updated"]):
            print("下載 PDF:", m["date"], m["title"])
            b64 = get(f"{API}?pdf={m['id']}").decode()
            if b64.startswith("ERR"):
                raise SystemExit(b64)
            open(path, "wb").write(base64.b64decode(b64))
            downloaded = True

        if downloaded or not os.path.exists(path):
            anonymize_pdf(path, all_staff_names)
            optimize_pdf(path)

        enriched = enrich_meeting(m)
        
        # 抽取實體圖片檔
        dest_dir = os.path.join(IMG_BASE_DIR, m["id"])
        imgs = extract_pdf_images(path, dest_dir)
        enriched["images"] = [f"data/images/{m['id']}/{f}" for f in imgs]

        # 針對全文與各項連結標題執行姓名去中間字去識別化
        masked_text = enriched.get("text", "")
        for n in all_staff_names:
            masked_text = masked_text.replace(n, mask_name(n))
        enriched["text"] = masked_text

        for link in enriched.get("links", []):
            t = link.get("title", "")
            for n in all_staff_names:
                t = t.replace(n, mask_name(n))
            link["title"] = t
        
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
    print("同步、去識別化、圖片抽取與結構化分析完成，共", len(enriched_list), "份會議")

if __name__ == "__main__":
    main()
