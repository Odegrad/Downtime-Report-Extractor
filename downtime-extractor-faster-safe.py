################# LIBRARIES
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import os
import glob
import json
from selenium.webdriver.common.action_chains import ActionChains
from datetime import datetime
from selenium.webdriver.chrome.options import Options

# Core tools for explicit, dynamic waiting
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

################# CONFIGURATION
### Set retries to download
MAX_RETRIES = 3
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
    script_dir = os.path.dirname(os.path.abspath(__file__))
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
chrome_options.add_argument("--headless=new") # So the driver doesnt pop up on the screen
# Force a standard monitor resolution so the UI doesn't collapse
chrome_options.add_argument("--window-size=1920,1080") 

def get_file_count():
    """Helper to count excel files in the folder."""
    return len(glob.glob(os.path.join(folder_path, "*.xlsx")))

################# MAIN ACCOUNT LOOP 
for email, pwd in accounts.items():
    attempt = 0
    success = False

    while attempt < MAX_RETRIES and not success:
        attempt += 1
        print(f"\n-----Processing {email} (Attempt {attempt}/{MAX_RETRIES})-----")
        
        # Start the driver inside the retry loop so each retry starts fresh
        prefs = {"download.default_directory": folder_path}
        chrome_options.add_experimental_option("prefs", prefs)
        driver = webdriver.Chrome(options=chrome_options)
        
        # Dedicated engine to handle dynamic UI rendering limits (max 15s wait)
        wait = WebDriverWait(driver, 15)
        
        try:
            driver.execute_cdp_cmd('Page.setDownloadBehavior', {
                'behavior': 'allow', 
                'downloadPath': folder_path
            })
            driver.implicitly_wait(10)
            
            # 1. LOGIN
            driver.get("https://example.com/login")
            
            # Enter Credentials (Wait safely for the DOM entry point)
            try:
                username_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
                username_field.send_keys(email)
            except TimeoutException:
                driver.delete_all_cookies()
                driver.refresh()
                username_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
                username_field.send_keys(email)
                
            driver.find_element(By.ID, "password").send_keys(pwd)
            driver.find_element(By.ID, "J_userLogin_btn").click()
            
            # Smart Wait: Wait for the login button to vanish, confirming authentication redirect is handling cleanly
            wait.until(EC.invisibility_of_element_located((By.ID, "J_userLogin_btn")))

            # 2. NAVIGATE & EXPORT
            driver.get("https://example.com/monitoring")

            # Handle "Got it" banner 
            try:
                got_it_btn = WebDriverWait(driver, 7).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "button.version-btn"))
                )
                driver.execute_script("arguments[0].click();", got_it_btn)
                print(f"[+] Successfully dismissed 'New Version' modal for {email}")
            except TimeoutException:
                print(f"[-] No 'New Version' modal detected for {email}. Moving on...")

            # Click APs (Wait dynamically for the menu item to become interactive)
            aps_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[text()='APs']")))
            aps_btn.click()

            # Trigger Export
            initial_count = get_file_count()
            export_xpath = "//*[local-name()='use' and contains(@*,'#ic-export')]/ancestor::span"
            
            # Ensure the export action target is present in the DOM tree
            export_btn = wait.until(EC.presence_of_element_located((By.XPATH, export_xpath)))
            
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", export_btn)
            time.sleep(1) # Small 1s buffer allowed here to let lazy UI layout settle post-scroll
            driver.execute_script("arguments[0].click();", export_btn)
            
            print(f"Export clicked. Waiting for file...")
            
            # Verification Loop: Wait up to 30s for a new file to appear
            for _ in range(30):
                time.sleep(1) # System loop checking file growth sequentially
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
                print(f"Retrying in 5 seconds...")
                time.sleep(5)

    if not success:
        print(f"SKIPPING: {email} failed after {MAX_RETRIES} attempts.")

################## MASTER FILE PORTION ##############################
import pandas as pd
import glob
import os
import time

# Give the last download a few extra seconds to finalize writing to disk
print("Waiting for final downloads to settle...")
time.sleep(5)

# 1. Setup paths
download_path = folder_path 
export_pattern = os.path.join(download_path, "*.xlsx") 

# 2. Get list of files
file_list = glob.glob(export_pattern)

if not file_list:
    print(f"CRITICAL: No Excel files found in {download_path}. Did the downloads finish?")
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
        # Combine
        final_df = pd.concat(combined_data, axis=0, ignore_index=True)
        
        # Save with a full path to ensure you know where it is
        output_name = os.path.join(download_path, "Master_Report.xlsx")
        final_df.to_excel(output_name, index=False)
        print(f"SUCCESS: Created {output_name}")
    else:
        print("No data was loaded into the list.")
