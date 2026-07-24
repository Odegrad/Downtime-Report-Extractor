# Internal Report Export Automation

This project is an internal automation utility for authorized use only. It automates routine reporting tasks in a cloud-based management portal by logging in with approved credentials, navigating to the relevant monitoring pages, and downloading Excel reports into a date-based folder.

## 🚀 Purpose

This tool is intended for internal operational workflows where report export automation is needed. It is designed to reduce manual effort while keeping credentials and exported files local and secure.

## 🔧 Features

- Uses Selenium to automate browser actions
- Supports multiple authorized accounts
- Saves downloaded reports into a date-based folder
- Uses a local credentials file so sensitive values are not committed to GitHub
- Runs in headless Chrome mode for a cleaner experience

## 🧰 Requirements

- Python 3
- Selenium
- Google Chrome
- ChromeDriver compatible with your installed Chrome version

## ⚙️ Setup

1. Install Python dependencies:
   ```bash
   pip install selenium
   ```

2. Create a local credentials file named `credentials.json` in the project folder:
   ```json
   {
     "your_email@example.com": "your_password"
   }
   ```

3. Run the script:
   ```bash
   python report-export-automation.py
   ```

## 🧠 How It Works

1. The script opens the target login page.
2. It signs in using credentials from `credentials.json`.
3. It navigates to the required monitoring pages.
4. It downloads the requested Excel reports into a folder named after today’s date.

## 📝 Notes

- Exported files are saved in a folder named after today’s date.
- `credentials.json` is intentionally ignored by Git to protect your login details.
- This project should only be used for authorized internal workflows.

## 🔒 Security

Do not commit real passwords or secrets to GitHub. Keep sensitive values in local files or environment variables, and only use this tool for accounts you are authorized to access.

## 📸 Screenshot


