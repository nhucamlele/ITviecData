"""
itviec_scraper.py
Crawl IT jobs từ itviec.com với:
- undetected-chromedriver
- login bằng cookie (hoặc thủ công lần đầu)
- append dữ liệu mới lên đầu file JSON
- skip link trùng
- push GitHub tự động
"""

import os
import time
import random
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==== CONFIG ====
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"

EXPORTED_CHROME_COOKIES = Path("chrome_cookies.json")
COOKIE_PATH = Path("itviec_cookies.json")
OUT_PATH = Path(r"D:\projects\ITViecData\itviec_it_filtered.json")

REPO_PATH = Path(r"D:\projects\ITViecData")
REPO_URL = "https://github.com/nhucamlele/ITViecData.git"

WAIT_TIMEOUT = 20
DEFAULT_PAGES = 3  # có thể đổi số trang

# ==== DRIVER ====
def init_uc_driver(headless=False):
    options = uc.ChromeOptions()
    options.add_argument(f"--user-agent={USER_AGENT}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
    driver = uc.Chrome(options=options)
    wait = WebDriverWait(driver, WAIT_TIMEOUT)
    return driver, wait

# ==== COOKIE ====
def import_chrome_cookies(driver, cookie_json_path: Path, domain_hint="itviec.com"):
    if not cookie_json_path.exists():
        return False
    with cookie_json_path.open("r", encoding="utf-8") as f:
        cookies = json.load(f)
    driver.get(f"https://{domain_hint}")
    added = 0
    for c in cookies:
        try:
            driver.add_cookie({"name": c["name"], "value": c["value"]})
            added += 1
        except:
            pass
    driver.refresh()
    print(f"✅ Đã import {added} cookie từ {cookie_json_path}")
    return added > 0

def load_cookies_json(driver, path: Path, domain_hint="itviec.com"):
    if not path.exists():
        return False
    with path.open("r", encoding="utf-8") as f:
        cookies = json.load(f)
    driver.get(f"https://{domain_hint}")
    added = 0
    for c in cookies:
        try:
            driver.add_cookie({"name": c["name"], "value": c["value"]})
            added += 1
        except:
            pass
    driver.refresh()
    print(f"✅ Đã load {added} cookie từ {path}")
    return added > 0

def save_cookies_json(driver, path: Path):
    cookies = driver.get_cookies()
    with path.open("w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"✅ Đã lưu {len(cookies)} cookie vào {path}")

def manual_login_and_save(driver, wait):
    driver.get("https://itviec.com/sign_in")
    print("➡️ Đăng nhập thủ công, sau đó quay lại terminal và nhấn Enter.")
    input("Nhấn Enter khi đã đăng nhập xong...")
    save_cookies_json(driver, COOKIE_PATH)

# ==== UTILITIES ====
def parse_posted_time(text):
    if not text:
        return ""
    text = text.lower().strip()
    now = datetime.now()
    m_days = re.search(r"(\d+)\s*day", text)
    if m_days:
        return (now - timedelta(days=int(m_days.group(1)))).strftime("%d/%m/%Y")
    m_hours = re.search(r"(\d+)\s*hour", text)
    if m_hours:
        return (now - timedelta(hours=int(m_hours.group(1)))).strftime("%d/%m/%Y")
    if "today" in text:
        return now.strftime("%d/%m/%Y")
    if "yesterday" in text:
        return (now - timedelta(days=1)).strftime("%d/%m/%Y")
    return ""

# ==== GET JOB LIST ====
def get_job_list(driver, wait, pages=DEFAULT_PAGES):
    pattern_valid = re.compile(r"https?://itviec\.com/it-jobs/[^/?#]+-\d+$", re.IGNORECASE)
    all_job_urls = set()

    for page in range(1, pages + 1):
        url = f"https://itviec.com/it-jobs?page={page}"
        print("Mở:", url)
        driver.get(url)
        time.sleep(random.uniform(2, 4))

        elems = driver.find_elements(By.XPATH, "//*[@data-search--job-selection-job-url-value]")
        for e in elems:
            try:
                slug = e.get_attribute("data-search--job-selection-job-slug-value")
                if slug:
                    candidate = f"https://itviec.com/it-jobs/{slug}".split("?")[0]
                    if pattern_valid.match(candidate):
                        all_job_urls.add(candidate)
            except:
                pass

        anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='/it-jobs/']")
        for a in anchors:
            try:
                href = a.get_attribute("href")
                if href and pattern_valid.match(href.split("?")[0].split("#")[0]):
                    all_job_urls.add(href.split("?")[0])
            except:
                pass

        print(f"  -> Tích lũy {len(all_job_urls)} link.")
        time.sleep(random.uniform(1, 2))
    return list(all_job_urls)

# ==== CRAWL DETAIL ====
def crawl_job(driver, wait, url):
    job = {"Url": url}
    try:
        driver.get(url)
        time.sleep(random.uniform(1.5, 2.5))

        job["Job name"] = driver.find_element(By.CSS_SELECTOR, "h1.ipt-xl-6.text-it-black").text.strip()
        job["Company Name"] = driver.find_element(By.CSS_SELECTOR, "div.employer-name").text.strip()
        job["Address"] = driver.find_element(By.CSS_SELECTOR, "span.normal-text.text-rich-grey").text.strip()
        job["Company type"] = driver.find_element(By.CSS_SELECTOR, "span.normal-text.text-rich-grey.ms-1").text.strip()

        # posted date
        try:
            time_text = driver.find_element(By.XPATH, "//span[contains(text(),'Posted')]").text.strip()
            job["Time"] = parse_posted_time(time_text)
        except:
            job["Time"] = ""

        # skills
        skills = [el.text.strip() for el in driver.find_elements(By.CSS_SELECTOR, "div.d-flex.flex-wrap.igap-2 a") if el.text.strip()]
        job["Skills"] = ", ".join(skills)

        # salary
        try:
            job["Salary"] = driver.find_element(By.CSS_SELECTOR, "div.salary span").text.strip()
        except:
            try:
                job["Salary"] = driver.find_element(By.CSS_SELECTOR, "div.salary").text.strip()
            except:
                job["Salary"] = ""

        # company info
        job["Company industry"] = ""
        job["Company size"] = None
        job["Working days"] = ""
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, "div.imt-4 div.row")
            for row in rows:
                label = row.find_element(By.CSS_SELECTOR, "div.col.text-dark-grey").text.strip().lower()
                value = row.find_element(By.CSS_SELECTOR, "div.col.text-end.text-it-black").text.strip()
                if "industry" in label:
                    job["Company industry"] = value
                elif "size" in label:
                    job["Company size"] = value
                elif "working day" in label:
                    job["Working days"] = value
        except:
            pass

    except Exception as e:
        print("⚠️ Lỗi crawl:", e)

    return job

# ==== MAIN ====
def main():
    print("=== ITVIEC SCRAPER (skip duplicates + append + git push) ===")
    driver, wait = init_uc_driver(headless=False)

    try:
        # ---- Login / load cookie ----
        if EXPORTED_CHROME_COOKIES.exists():
            import_chrome_cookies(driver, EXPORTED_CHROME_COOKIES)
        elif COOKIE_PATH.exists():
            load_cookies_json(driver, COOKIE_PATH)
        else:
            manual_login_and_save(driver, wait)

        # ---- Load existing jobs ----
        existing_jobs = []
        seen_urls = set()
        if OUT_PATH.exists():
            with OUT_PATH.open("r", encoding="utf-8") as f:
                existing_jobs = json.load(f)
                seen_urls = {j["Url"] for j in existing_jobs if "Url" in j}
            print(f"📂 Đã load {len(existing_jobs)} job cũ.")

        # ---- Get new job links ----
        job_links = get_job_list(driver, wait, pages=DEFAULT_PAGES)
        print(f"🔗 Tìm được {len(job_links)} link mới (trước khi lọc trùng).")

        # ---- Lọc trùng ----
        new_links = [u for u in job_links if u not in seen_urls]
        print(f"🆕 Có {len(new_links)} job mới cần crawl.")

        # ---- Crawl chi tiết ----
        new_jobs = []
        for i, link in enumerate(new_links, 1):
            print(f"[{i}/{len(new_links)}] Crawl: {link}")
            job = crawl_job(driver, wait, link)
            new_jobs.append(job)
            time.sleep(random.uniform(1.5, 3))

        # ---- Merge: chèn lên đầu ----
        jobs = new_jobs + existing_jobs

        # ---- Save ----
        with OUT_PATH.open("w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        print(f"✅ Lưu tổng cộng {len(jobs)} job vào {OUT_PATH}")

        # ---- Push lên GitHub ----
        print("🚀 Đang đẩy dữ liệu lên GitHub...")
        os.chdir(REPO_PATH)
        subprocess.run(["git", "add", "."], check=False)
        subprocess.run(["git", "commit", "-m", f"update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"], check=False)
        subprocess.run(["git", "push", "origin", "main"], check=False)
        print("🎉 Đã push lên GitHub thành công!")

    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()
