"""
itviec_crawler_with_login_and_gitpush.py
(Fixed: multi-page + formatted JSON output)
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

# ==== CONFIG ====
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"

EXPORTED_CHROME_COOKIES = Path("chrome_cookies.json")
COOKIE_PATH = Path("itviec_cookies.json")

OUT_PATH = Path(r"D:\projects\ITViecData\itviec_jobs_data.json")

REPO_PATH = Path(r"D:\projects\ITViecData")
REPO_URL = "https://github.com/nhucamlele/ITViecData.git"

WAIT_TIMEOUT = 20
DEFAULT_PAGES = 5


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
def load_cookies(driver):
    if EXPORTED_CHROME_COOKIES.exists():
        with open(EXPORTED_CHROME_COOKIES, "r", encoding="utf-8") as f:
            cookies = json.load(f)
    elif COOKIE_PATH.exists():
        with open(COOKIE_PATH, "r", encoding="utf-8") as f:
            cookies = json.load(f)
    else:
        driver.get("https://itviec.com/sign_in")
        print("➡️ Đăng nhập thủ công rồi nhấn Enter...")
        input("Nhấn Enter khi đăng nhập xong...")
        cookies = driver.get_cookies()
        with open(COOKIE_PATH, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
    driver.get("https://itviec.com")
    for c in cookies:
        try:
            driver.add_cookie({"name": c["name"], "value": c["value"]})
        except:
            pass
    driver.refresh()


# ==== UTIL ====
def parse_posted_time(text):
    if not text:
        return ""
    text = text.lower().strip()
    now = datetime.now()
    if "today" in text:
        return now.strftime("%Y-%m-%d")
    if "yesterday" in text:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    m = re.search(r"(\d+)\s*day", text)
    if m:
        return (now - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
    m = re.search(r"(\d+)\s*hour", text)
    if m:
        return (now - timedelta(hours=int(m.group(1)))).strftime("%Y-%m-%d")
    return ""


# ==== JOB LIST ====
def get_job_list(driver, pages=DEFAULT_PAGES):
    pattern = re.compile(r"https?://itviec\.com/it-jobs/[^/?#]+-\d+$", re.IGNORECASE)
    urls = set()

    for page in range(1, pages + 1):
        url = f"https://itviec.com/it-jobs?page={page}"
        print(f"📄 Đang mở trang {page}: {url}")
        driver.get(url)
        time.sleep(random.uniform(3, 5))

        anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='/it-jobs/']")
        for a in anchors:
            href = a.get_attribute("href")
            if href and pattern.match(href.split("?")[0]):
                urls.add(href.split("?")[0])

        print(f"  -> Tổng cộng {len(urls)} link tích lũy.")
    return list(urls)


# ==== CRAWL DETAIL ====
def crawl_job(driver, url):
    job_data = {}
    try:
        driver.get(url)
        time.sleep(random.uniform(2, 3))

        job_name = driver.find_element(By.CSS_SELECTOR, "h1.ipt-xl-6.text-it-black").text.strip()
        company = driver.find_element(By.CSS_SELECTOR, "div.employer-name").text.strip()
        address = driver.find_element(By.CSS_SELECTOR, "span.normal-text.text-rich-grey").text.strip()
        work_type = driver.find_element(By.CSS_SELECTOR, "span.normal-text.text-rich-grey.ms-1").text.strip()

        try:
            posted_text = driver.find_element(By.XPATH, "//span[contains(text(),'Posted')]").text.strip()
            posted_time = parse_posted_time(posted_text)
        except:
            posted_time = ""

        skills = [el.text.strip() for el in driver.find_elements(By.CSS_SELECTOR, "div.d-flex.flex-wrap.igap-2 a") if el.text.strip()]

        try:
            salary = driver.find_element(By.CSS_SELECTOR, "div.salary span").text.strip()
        except:
            try:
                salary = driver.find_element(By.CSS_SELECTOR, "div.salary").text.strip()
            except:
                salary = ""

        company_industry, company_size, working_days = "", "", ""
        rows = driver.find_elements(By.CSS_SELECTOR, "div.imt-4 div.row")
        for row in rows:
            try:
                label = row.find_element(By.CSS_SELECTOR, "div.col.text-dark-grey").text.strip().lower()
                value = row.find_element(By.CSS_SELECTOR, "div.col.text-end.text-it-black").text.strip()
                if "industry" in label:
                    company_industry = value
                elif "size" in label:
                    company_size = value
                elif "working day" in label:
                    working_days = value
            except:
                continue

        # ✅ TRẢ VỀ DẠNG BẠN YÊU CẦU
        job_data = {
            "Url": url,
            "Job name": job_name,
            "Company Name": company,
            "Address": address,
            "Company type": work_type,
            "Time": posted_time,
            "Skills": skills,
            "Salary": salary,
            "Company industry": company_industry,
            "Company size": company_size,
            "Working days": working_days,
        }

    except Exception as e:
        print(f"⚠️ Lỗi khi crawl {url}: {e}")
    return job_data


# ==== MAIN ====
def main():
    print("=== ITVIEC SCRAPER (formatted JSON + git push) ===")
    driver, wait = init_uc_driver(headless=False)
    try:
        load_cookies(driver)

        # Load cũ nếu có
        existing = []
        seen = set()
        if OUT_PATH.exists():
            with OUT_PATH.open("r", encoding="utf-8") as f:
                existing = json.load(f)
                seen = {j["Url"] for j in existing}
            print(f"📂 Đã load {len(existing)} job cũ.")

        # Lấy danh sách link mới
        job_links = get_job_list(driver, pages=DEFAULT_PAGES)
        new_links = [u for u in job_links if u not in seen]
        print(f"🆕 Có {len(new_links)} job mới cần crawl.")

        results = existing[:]
        for i, link in enumerate(new_links, 1):
            print(f"[{i}/{len(new_links)}] Crawl: {link}")
            data = crawl_job(driver, link)
            if data:
                results.append(data)

        with OUT_PATH.open("w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"✅ Đã lưu {len(results)} job vào {OUT_PATH}")

        # GIT PUSH
        os.chdir(REPO_PATH)
        subprocess.run(["git", "add", "."], check=False)
        subprocess.run(["git", "commit", "-m", f"update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"], check=False)
        subprocess.run(["git", "push", "origin", "main"], check=False)
        print("🎉 Đã push lên GitHub thành công!")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
