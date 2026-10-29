"""從 Apps Script 同步會議索引與 PDF 到 data/，供 GitHub Pages 直接提供（快速、無流量限制）。"""
import base64, json, os, urllib.request

API = os.environ.get("API_URL") or open("index.html", encoding="utf-8").read().split("const API_URL = '")[1].split("'")[0]
ROOT = os.path.join(os.path.dirname(__file__), "..", "data")
PDF_DIR = os.path.join(ROOT, "pdf")
os.makedirs(PDF_DIR, exist_ok=True)

def get(url):
    with urllib.request.urlopen(url, timeout=300) as r:
        return r.read()

new = json.loads(get(API))
idx_path = os.path.join(ROOT, "index.json")
old = {m["id"]: m for m in json.load(open(idx_path, encoding="utf-8"))} if os.path.exists(idx_path) else {}

for m in new:
    path = os.path.join(PDF_DIR, m["id"] + ".pdf")
    if os.path.exists(path) and old.get(m["id"], {}).get("updated") == m["updated"]:
        continue
    print("下載", m["date"], m["title"])
    b64 = get(f"{API}?pdf={m['id']}").decode()
    if b64.startswith("ERR"):
        raise SystemExit(b64)
    open(path, "wb").write(base64.b64decode(b64))

keep = {m["id"] + ".pdf" for m in new}
for f in os.listdir(PDF_DIR):
    if f not in keep:
        print("移除", f); os.remove(os.path.join(PDF_DIR, f))

json.dump(new, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False)
print("完成，共", len(new), "份")
