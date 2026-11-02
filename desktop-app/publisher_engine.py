#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
會議資料庫 — 桌面發布核心處理引擎
負責接收 PDF 檔案、結構化分析、PII 去識別化脫敏、抽取圖片、更新 index.json 並推送到 GitHub。
"""
import sys
import os
import json
import re
import shutil
import subprocess
import hashlib

# 專案根目錄
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
PDF_DIR = os.path.join(DATA_DIR, "pdf")
IMG_DIR = os.path.join(DATA_DIR, "images")
INDEX_PATH = os.path.join(DATA_DIR, "index.json")

# 引入現有 scripts/sync.py 中的成熟工具
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
from sync import (
    KNOWN_DEPTS,
    extract_pdf_images,
    extract_clean_links,
    sanitize_pii,
    enrich_meeting,
    clean_url,
    get_domain,
    parse_meeting_filename
)

def generate_file_id(date_str, title_str):
    """根據日期與乾淨標題生成穩定的 ID"""
    clean_title, _ = parse_meeting_filename(title_str)
    h = hashlib.sha1(f"{date_str}_{clean_title}".encode('utf-8')).hexdigest()
    # 仿照 Google Drive ID 格式（28~33 碼英數字）
    return f"1pub_{date_str.replace('-', '')}_{h[:16]}"

def publish_meeting(pdf_path, date_str, title_str, raw_text, gdrive_dir=None):
    """
    執行單份會議的發布流程（支援 1版、2版、3版 智慧版本辨識與自動覆蓋舊版）
    """
    clean_title, version = parse_meeting_filename(title_str)
    ver_tag = f" [{version}]" if version else ""
    print(f"[1/5] 驗證檔案與準備發布: {date_str} {clean_title}{ver_tag}")
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"找不到指定的 PDF 檔案: {pdf_path}")

    os.makedirs(PDF_DIR, exist_ok=True)
    os.makedirs(IMG_DIR, exist_ok=True)

    # 1. 如果有指定 Google Drive 資料夾，複製一份過去完成第一網站(雲端硬碟)發布
    if gdrive_dir and os.path.exists(gdrive_dir):
        # 雲端硬碟保留使用者原始版本標籤，例如 2026-09-02_擴大行政會議 (4版).pdf
        dest_filename = os.path.basename(pdf_path)
        if not dest_filename.startswith(date_str):
            dest_filename = f"{date_str}_{title_str}.pdf"
        gdrive_dest = os.path.join(gdrive_dir, dest_filename)
        shutil.copy2(pdf_path, gdrive_dest)
        print(f"[2/5] ✅ 已同步至 Google 雲端硬碟: {gdrive_dest}")
    else:
        print("[2/5] ℹ️ 未指定 Google 雲端硬碟或路徑未啟用，略過本機 Google Drive 複製")

    # 2. 複製 PDF 到專案 data/pdf/
    file_id = generate_file_id(date_str, clean_title)
    local_pdf_dest = os.path.join(PDF_DIR, f"{file_id}.pdf")
    shutil.copy2(pdf_path, local_pdf_dest)

    # 3. 抽取實體圖片 (包含表格截圖、照片宣導)
    meeting_img_dir = os.path.join(IMG_DIR, file_id)
    images = extract_pdf_images(local_pdf_dest, meeting_img_dir)
    image_paths = [f"data/images/{file_id}/{img}" for img in images]
    print(f"[3/5] ✅ 已抽取 {len(images)} 張內嵌實體相片與表格截圖")

    # 4. 結構化文字分析與 PII 學生個資脫敏
    sanitized_text = sanitize_pii(raw_text)
    meeting_obj = {
        "id": file_id,
        "date": date_str,
        "title": clean_title,
        "url": f"data/pdf/{file_id}.pdf",
        "updated": subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%S.000Z"]).decode().strip(),
        "text": sanitized_text,
        "images": image_paths
    }
    if version:
        meeting_obj["version"] = version

    meeting_obj = enrich_meeting(meeting_obj)

    # 5. 更新 data/index.json（若同日已有同名會議，自動以新版本覆蓋）
    all_meetings = []
    if os.path.exists(INDEX_PATH):
        try:
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                all_meetings = json.load(f)
        except Exception:
            all_meetings = []

    # 檢查是否已有相同日期與標題的會議，有則以最新版本覆蓋，無則新增
    updated = False
    for i, m in enumerate(all_meetings):
        if m.get("date") == date_str and m.get("title") == clean_title:
            all_meetings[i] = meeting_obj
            updated = True
            print(f"🔄 偵測到已有 {date_str} {clean_title}，已自動覆蓋更新為最新修訂版{ver_tag}")
            break
    if not updated:
        all_meetings.append(meeting_obj)

    # 依日期遞減排序（最新置頂）
    all_meetings.sort(key=lambda x: x.get("date", ""), reverse=True)

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(all_meetings, f, ensure_ascii=False, indent=2)

    print(f"[4/5] ✅ 會議資料庫索引已更新 (目前共 {len(all_meetings)} 份會議)")

    # 6. 推送至 GitHub Pages (第二網站推播部署)
    print("[5/5] 🚀 正在推送至 GitHub 進行線上部署...")
    commit_msg = f"publish: {date_str} {clean_title}{ver_tag} (via MeetingPublisher Desktop)"
    try:
        subprocess.run(["git", "add", "data/"], cwd=PROJECT_ROOT, check=True)
        # 檢查是否有更動需要 commit
        diff_res = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=PROJECT_ROOT)
        if diff_res.returncode != 0:
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=PROJECT_ROOT, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=PROJECT_ROOT, check=True)
            print("✅ 成功推送到 GitHub！GitHub Pages 正在自動發布部署中。")
        else:
            print("ℹ️ 資料無變更，無需額外提交至 Git。")
    except Exception as e:
        print(f"⚠️ Git 提交或推送失敗: {e}", file=sys.stderr)
        raise

    return meeting_obj

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  desktop_publisher.py --publish <pdf_path> --date <YYYY-MM-DD> --title <TITLE> [--text-file <txt_path>] [--gdrive <dir>]")
        print("  desktop_publisher.py --sync")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "--sync":
        # 呼叫現有的 sync.py
        sync_script = os.path.join(PROJECT_ROOT, "scripts", "sync.py")
        res = subprocess.run([sys.executable, sync_script], cwd=PROJECT_ROOT)
        sys.exit(res.returncode)

    elif cmd == "--publish":
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--publish", dest="pdf_path", required=True)
        parser.add_argument("--date", required=True)
        parser.add_argument("--title", required=True)
        parser.add_argument("--text-file", default=None)
        parser.add_argument("--gdrive", default=None)
        args = parser.parse_args(sys.argv[1:])

        raw_text = ""
        if args.text_file and os.path.exists(args.text_file):
            with open(args.text_file, "r", encoding="utf-8") as f:
                raw_text = f.read()

        try:
            publish_meeting(args.pdf_path, args.date, args.title, raw_text, args.gdrive)
            print("SUCCESS")
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
