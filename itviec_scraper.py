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

COOKIE_PATH = Path("itviec_cookies.json")
OUT_PATH = Path(r"D:\projects\ITViecData\itviec_it_filtered.json")

REPO_PATH = Path(r"D:\projects\ITViecData")
REPO_URL = "https://github.com/nhucamlele/ITViecData.git"

WAIT_TIMEOUT = 20
DEFAULT_PAGES = 3  # số trang crawl

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
def load_cookies(driver, path: Path, domain="itviec.com"):
    if not path.exists():
        return False
    with path.open("r", encoding="utf-8") as f:
        cookies = json.load(f)
    driver.get(f"https://{domain}")
    added = 0
    for c in cookies:
        try:
            driver.add_cookie({"name": c["name"], "value": c["value"], "domain": c.get("domain")})
            added += 1
        except:
            pass
    driver.refresh()
    print(f"✅ Load {added} cookie từ {path}")
    return added > 0

def save_cookies(driver, path: Path):
    cookies = driver.get_cookies()
    with path.open("w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"✅ Lưu {len(cookies)} cookie vào {path}")

def manual_login_and_save(driver):
    driver.get("https://itviec.com/sign_in")
    print("➡️ Đăng nhập thủ công, sau đó quay lại terminal và nhấn Enter.")
    input("Nhấn Enter khi đã đăng nhập xong...")
    save_cookies(driver, COOKIE_PATH)

# ==== UTIL ====
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
        return now.strftime("%d/%m/%Y")
    if "today" in text:
        return now.strftime("%d/%m/%Y")
    if "yesterday" in text:
        return (now - timedelta(days=1)).strftime("%d/%m/%Y")
    return ""

# ==== GET JOB LIST ====
def get_job_list(driver, pages=DEFAULT_PAGES):
    pattern_valid = re.compile(r"https?://itviec\.com/it-jobs/[^/?#]+-\d+$", re.IGNORECASE)
    all_job_urls = set()
    for page in range(1, pages+1):
        url = f"https://itviec.com/it-jobs?page={page}"
        print("Mở:", url)
        driver.get(url)
        time.sleep(random.uniform(2,4))
        elems = driver.find_elements(By.XPATH, "//*[@data-search--job-selection-job-url-value]")
        for e in elems:
            try:
                slug = e.get_attribute("data-search--job-selection-job-slug-value")
                if slug:
                    candidate = f"https://itviec.com/it-jobs/{slug}".split("?")[0]
                    if pattern_valid.match(candidate):
                        all_job_urls.add(candidate)
            except: pass
        anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='/it-jobs/']")
        for a in anchors:
            try:
                href = a.get_attribute("href")
                if href and pattern_valid.match(href.split("?")[0].split("#")[0]):
                    all_job_urls.add(href.split("?")[0])
            except: pass
        print(f"  -> Tích lũy {len(all_job_urls)} link.")
        time.sleep(random.uniform(1,2))
    return list(all_job_urls)

# ==== CRAWL DETAIL ====
def crawl_job(driver, url):
    job = {
        "Url": url,
        "Job name": "",
        "Company Name": "",
        "Address": "",
        "Company type": "",
        "Time": "",
        "Skills": "",
        "Salary": "",
        "Company industry": "",
        "Company size": None,
        "Working days": ""
    }
    try:
        driver.get(url)
        time.sleep(random.uniform(1.5,2.5))
        job["Job name"] = driver.find_element(By.CSS_SELECTOR,"h1.ipt-xl-6.text-it-black").text.strip()
        job["Company Name"] = driver.find_element(By.CSS_SELECTOR,"div.employer-name").text.strip()
        job["Address"] = driver.find_element(By.CSS_SELECTOR,"span.normal-text.text-rich-grey").text.strip()
        job["Company type"] = driver.find_element(By.CSS_SELECTOR,"span.normal-text.text-rich-grey.ms-1").text.strip()
        # posted date
        try:
            time_text = driver.find_element(By.XPATH,"//span[contains(text(),'Posted')]").text.strip()
            job["Time"] = parse_posted_time(time_text)
        except: pass
        # skills
        job["Skills"] = ", ".join([el.text.strip() for el in driver.find_elements(By.CSS_SELECTOR,"div.d-flex.flex-wrap.igap-2 a") if el.text.strip()])
        # salary
        try:
            job["Salary"] = driver.find_element(By.CSS_SELECTOR,"div.salary span").text.strip()
        except:
            try:
                job["Salary"] = driver.find_element(By.CSS_SELECTOR,"div.salary").text.strip()
            except: job["Salary"] = ""
        # company info
        try:
            rows = driver.find_elements(By.CSS_SELECTOR,"div.imt-4 div.row")
            for row in rows:
                label = row.find_element(By.CSS_SELECTOR,"div.col.text-dark-grey").text.strip().lower()
                value = row.find_element(By.CSS_SELECTOR,"div.col.text-end.text-it-black").text.strip()
                if "industry" in label:
                    job["Company industry"] = value
                elif "size" in label:
                    job["Company size"] = value
                elif "working day" in label:
                    job["Working days"] = value
        except: pass
    except Exception as e:
        print("⚠️ Lỗi crawl:", e)
    return job

# ==== MAIN ====
def main():
    driver, wait = init_uc_driver(headless=False)
    try:
        # login
        if not load_cookies(driver, COOKIE_PATH):
            manual_login_and_save(driver)

        # load existing
        existing_jobs = []
        seen_urls = set()
        if OUT_PATH.exists():
            with OUT_PATH.open("r", encoding="utf-8") as f:
                existing_jobs = json.load(f)
                seen_urls = {j["Url"] for j in existing_jobs if "Url" in j}
            print(f"📂 Load {len(existing_jobs)} job cũ")

        # get job list
        job_links = get_job_list(driver, pages=DEFAULT_PAGES)
        new_links = [u for u in job_links if u not in seen_urls]
        print(f"🆕 Có {len(new_links)} job mới")

        # crawl
        jobs = existing_jobs[:]
        for i, link in enumerate(new_links,1):
            print(f"[{i}/{len(new_links)}] Crawl: {link}")
            job = crawl_job(driver, link)
            jobs.append(job)
            time.sleep(random.uniform(1.5,3))

        # save
        with OUT_PATH.open("w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        print(f"✅ Lưu {len(jobs)} job vào {OUT_PATH}")

        # git push
        os.chdir(REPO_PATH)
        subprocess.run(["git","add","."], check=False)
        subprocess.run(["git","commit","-m",f"update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"], check=False)
        subprocess.run(["git","push","origin","main"], check=False)
        print("🎉 Push GitHub xong")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
