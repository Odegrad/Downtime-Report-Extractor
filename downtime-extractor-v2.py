################# LIBRARIES
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import os
import glob
import json
from datetime import datetime
from selenium.webdriver.chrome.options import Options

# Core tools for explicit, dynamic waiting
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

################# CONFIGURATION
### Set retries to download
MAX_RETRIES = 3
### Flip to True to hide the browser window
HEADLESS = True
### Direct regional login page (the global cloud.ruijienetworks.com redirect was the slow part)
LOGIN_URL = ("https://cloud-as.ruijienetworks.com/sso/login?service=https%3A%2F%2Fcloud-as.ruijienetworks.com"
             "%2Fwebproxy%2Fsso%2Fback%3Frewrite%3Doff%26back%3Dhttps%253A%252F%252Fcloud-as.ruijienetworks.com"
             "%252Fmacc5%252FadminIntl%252F%2523%252F")
DASHBOARD_URL = "https://cloud-as.ruijienetworks.com/macc5/adminIntl/#/monitor_overview_global_menu"
MASTER_NAME = "Master_Report.xlsx"

### Get today's date (e.g., 2026-04-18)
today = datetime.now().strftime('%Y-%m-%d')
script_dir = os.path.dirname(os.path.abspath(__file__))
folder_path = os.path.join(script_dir, today)

#################  Create the folder if it doesn't exist
if not os.path.exists(folder_path):
    os.makedirs(folder_path)
    print(f"Created folder for today: {folder_path}")

################# Credentials

def load_accounts():
    """Load credentials from a local untracked file or environment variables."""
    credentials_file = os.path.join(script_dir, "credentials.json")

    if os.path.exists(credentials_file):
        with open(credentials_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and data:
            return data
        raise ValueError("credentials.json must contain a JSON object of username/password pairs.")

    env_username = os.getenv("APP_USERNAME")
    env_password = os.getenv("APP_PASSWORD")
    if env_username and env_password:
        return {env_username: env_password}

    raise ValueError(
        "No credentials found. Create credentials.json (ignored by Git) or set APP_USERNAME/APP_PASSWORD."
    )


accounts = load_accounts()

################# Chrome Options
chrome_options = Options()
if HEADLESS:
    chrome_options.add_argument("--headless=new")
# Force a standard monitor resolution so the UI doesn't collapse
chrome_options.add_argument("--window-size=1920,1080")
# The Ruijie pages never fully "finish" loading from Selenium's point of view, which made
# driver.get() hang and clicks time out. "none" returns immediately; the explicit waits below do the rest.
chrome_options.page_load_strategy = "none"
chrome_options.add_experimental_option("prefs", {
    "download.default_directory": folder_path,
    "download.prompt_for_download": False,
})


def get_file_count():
    """Helper to count excel files in the folder (ignoring the master report)."""
    return len([f for f in glob.glob(os.path.join(folder_path, "*.xlsx"))
                if os.path.basename(f) != MASTER_NAME])


################# MAIN ACCOUNT LOOP
for email, pwd in accounts.items():
    attempt = 0
    success = False

    while attempt < MAX_RETRIES and not success:
        attempt += 1
        print(f"\n-----Processing {email} (Attempt {attempt}/{MAX_RETRIES})-----")

        # Start the driver inside the retry loop so each retry starts fresh
        driver = webdriver.Chrome(options=chrome_options)

        # Explicit waits only (no implicit wait, they don't mix well)
        wait = WebDriverWait(driver, 20)

        try:
            driver.execute_cdp_cmd('Page.setDownloadBehavior', {
                'behavior': 'allow',
                'downloadPath': folder_path
            })

            # 1. LOGIN
            print("Opening login page...")
            driver.get(LOGIN_URL)

            # Wait until the fields are actually usable, not just present in the DOM
            try:
                username_field = wait.until(EC.element_to_be_clickable((By.ID, "username")))
            except TimeoutException:
                driver.delete_all_cookies()
                driver.refresh()
                username_field = wait.until(EC.element_to_be_clickable((By.ID, "username")))
            username_field.send_keys(email)

            wait.until(EC.element_to_be_clickable((By.ID, "originalPassword"))).send_keys(pwd)
            wait.until(EC.element_to_be_clickable((By.ID, "J_userLogin_btn"))).click()
            print("Login submitted.")

            # Wait for the login button to vanish, confirming the redirect went through
            wait.until(EC.invisibility_of_element_located((By.ID, "J_userLogin_btn")))
            WebDriverWait(driver, 60).until(EC.url_contains("/macc5/adminIntl/"))
            # 2. NAVIGATE & EXPORT
            driver.get(DASHBOARD_URL)

            # "Got it" banner is cosmetic (the export works without it), so only wait briefly
            try:
                got_it_btn = WebDriverWait(driver, 4).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "button.version-btn"))
                )
                driver.execute_script("arguments[0].click();", got_it_btn)
                print(f"[+] Dismissed 'New Version' modal for {email}")
            except TimeoutException:
                print(f"[-] No 'New Version' modal detected for {email}. Moving on...")

            # Click APs (JS click so a leftover banner can't block it)
            aps_xpath = (By.XPATH, "//div[text()='APs']")
            driver.refresh()
            aps_btn = wait.until(EC.presence_of_element_located(aps_xpath))
            driver.execute_script("arguments[0].click();", aps_btn)

            # Trigger Export
            initial_count = get_file_count()
            export_xpath = "//*[local-name()='use' and contains(@*,'#ic-export')]/ancestor::span"

            export_btn = wait.until(EC.presence_of_element_located((By.XPATH, export_xpath)))

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", export_btn)
            time.sleep(1)  # Small buffer to let lazy UI layout settle post-scroll
            driver.execute_script("arguments[0].click();", export_btn)

            print("Export clicked. Waiting for file...")

            # Verification Loop: Wait up to 30s for a new file to appear
            for _ in range(30):
                time.sleep(1)
                if get_file_count() > initial_count:
                    print(f"Success: File detected for {email}")
                    success = True
                    break

            if not success:
                print(f"Warning: Clicked export but no file appeared for {email}.")

        except Exception as e:
            print(f"Error on attempt {attempt} for {email}: {e}")

        finally:
            driver.quit()
            if not success and attempt < MAX_RETRIES:
                print("Retrying in 5 seconds...")
                time.sleep(5)

    if not success:
        print(f"SKIPPING: {email} failed after {MAX_RETRIES} attempts.")

################## MASTER FILE PORTION ##############################
import pandas as pd

# Wait for any in-progress downloads to finish (max ~15s)
print("Waiting for final downloads to settle...")
for _ in range(15):
    if not glob.glob(os.path.join(folder_path, "*.crdownload")):
        break
    time.sleep(1)

# Exclude the master file so re-runs on the same day don't double-count it
file_list = [f for f in glob.glob(os.path.join(folder_path, "*.xlsx"))
             if os.path.basename(f) != MASTER_NAME]

if not file_list:
    print(f"CRITICAL: No Excel files found in {folder_path}. Did the downloads finish?")
else:
    combined_data = []
    print(f"Found {len(file_list)} files. Combining...")

    for file in file_list:
        try:
            df = pd.read_excel(file)
            df['Account_Source'] = os.path.basename(file)
            combined_data.append(df)
        except Exception as e:
            print(f"Error reading {file}: {e}")

    if combined_data:
        final_df = pd.concat(combined_data, axis=0, ignore_index=True)
        output_name = os.path.join(folder_path, MASTER_NAME)
        final_df.to_excel(output_name, index=False)
        print(f"SUCCESS: Created {output_name}")
    else:
        print("No data was loaded into the list.")

# Delete all leftover .crdownload files in the folder
for path in glob.glob(os.path.join(folder_path, "*.crdownload")):
    try:
        os.remove(path)
        print(f"Removed: {path}")
    except OSError as e:
        print(f"Could not remove {path}: {e}")
