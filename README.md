# ⚡ XENON — AI Browser Assistant

A powerful Chrome Sidepanel AI Assistant that automates web tasks seamlessly inside your host Chrome browser.

## 📋 Prerequisites
- **Windows OS**
- **Python 3.11 or newer** ([Download Python 3.11/3.12](https://www.python.org/downloads/))

---

## 🚀 Quick Start Guide (Windows)

### Step 1: Get XENON

- **Option A (Easiest — No Git Required)**:
  Click the green **`Code`** button at the top of this GitHub page -> **`Download ZIP`**, then extract the ZIP folder to your computer.

- **Option B (For Developers / Git users)**:
  ```bash
  git clone https://github.com/siva010505/XENON.git
  cd XENON
  ```

### Step 2: Run 1-Click Setup
Double-click **`setup.bat`** inside the project folder.

This automated script will:
- Install Python dependencies & Playwright Chromium automatically.
- Register the silent background server launcher in Windows Registry.
- Create a **`Xenon Chrome`** shortcut on your Desktop with debugging port `9222`, dedicated profile, and auto-loaded extension.

### Step 3: Launch & Use Xenon!
1. Double-click the **`Xenon Chrome`** shortcut on your Desktop.
2. Sign in to your Google / Gmail account in Chrome.
3. Open `chrome://extensions`, enable **Developer Mode** (top-right toggle), and click **Load unpacked** -> select the `extension` folder from this project directory.
4. Click the **Xenon** side panel icon in Chrome, enter your AI API Key in **Settings** once, and start giving tasks!

---

## ✨ Key Features

- **Chrome Side Panel Interface**: Clean, modern responsive side panel UI built for Chrome.
- **Silent Background Server**: Server boots automatically in 100% hidden background mode with zero visible terminal windows.
- **Personal Info Autofill**: Store personal details (Full Name, DOB, Email, Phone, Address, etc.) securely in a dedicated Settings sub-page for automatic form filling.
- **Multi-LLM Provider Support**: Supports Google Gemini, OpenAI, Anthropic, DeepSeek, Ollama, and more.
- **Vision & Interactive Automation**: Uses vision and DOM inspection to search, navigate, fill forms, extract data, and execute complex multi-step browser tasks.
