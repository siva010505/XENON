# Xenon Browser Agent

Xenon is a powerful, autonomous AI web automation assistant. Powered by state-of-the-art LLMs (Gemini / DeepSeek NIM) and the `browser-use` framework, Xenon allows you to automate complex browser tasks directly from a sleek, minimalist Chrome Extension side-panel.

## 🚀 Features

- **Autonomous Navigation**: Give Xenon a task (like "Apply to this job" or "Extract the top 5 trending posts"), and it will autonomously navigate, click, type, and extract data.
- **Invisible Auto-Start Server**: Using Chrome Native Messaging, the Python backend server spins up completely invisibly in the background the moment you open your browser. No persistent terminals needed!
- **Voice Dictation**: Built-in Web Speech API voice typing with intelligent silence-detection and visual soundwaves.
- **Strict Tab Isolation**: Xenon is strictly locked to the tab you invoke it on, preventing it from wandering into unrelated background tabs or disrupting your personal browsing.
- **Liquid UI**: A clean, minimalist React interface featuring auto-expanding inputs, smooth cloudy scroll-masks, dynamic button states, and edge-lighting visual feedback during processing.
- **WebSocket Streaming**: Real-time status updates and agent actions are streamed directly to the UI, keeping you informed at every step.
- **Tiered Fallback Engine**: If the primary LLM fails or hits rate limits, Xenon automatically falls back to secondary API keys to ensure your task completes.

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, WebSockets, `browser-use` (Playwright/CDP), Chrome Native Messaging
- **Frontend (Extension)**: React, Vite, Vanilla CSS
- **AI Models**: Google Gemini (`gemini-3.1-flash-lite`, `gemini-3.5-flash`), DeepSeek via NVIDIA NIM

## 📦 Setup & Installation

### 1. Backend Dependencies
Ensure you have Python installed, then navigate to the `backend` directory and install the dependencies:
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Build the Extension
Navigate to the `extension` directory and build the React app.
```bash
cd extension
npm install
npm run build
```

### 3. Load the Extension into Chrome
1. Open Chrome and navigate to `chrome://extensions/`.
2. Turn on **Developer mode** and click **Load unpacked**. 
3. Select the `extension/dist` folder.
4. **Copy the 32-letter Extension ID** that is generated for Xenon.

### 4. Install Native Messaging Host
To allow the extension to automatically start the backend server in the background:
1. Double-click `install_native_host.bat` in the root folder.
2. Paste the Extension ID when prompted.
3. The script will securely register the Python host in your Windows Registry.

### 5. Chrome Debugging Setup
Xenon connects to your live Chrome instance using the Chrome DevTools Protocol (CDP). You must launch Chrome with remote debugging enabled. Run the provided batch script to launch your dedicated Chrome instance:
```bash
Launch_Chrome.bat
```

## 🔑 Environment Variables
Create a `.env` file in the `backend/` directory with your API keys:
```env
GEMINI_API_KEY=your_primary_key
GEMINI_API_KEY_2=your_fallback_key
NVIDIA_API_KEY=your_nim_key
```

You can also create a `personal_info.json` in the root directory to provide the agent with context for automatically filling out forms (like job applications).

## 📄 License
MIT License
