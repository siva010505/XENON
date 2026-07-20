# Xenon Browser Agent

Xenon is a powerful, autonomous AI web automation assistant. Powered by state-of-the-art LLMs (Gemini / DeepSeek NIM) and the `browser-use` framework, Xenon allows you to automate complex browser tasks directly from a sleek, minimalist Chrome Extension side-panel.

## 🚀 Features

- **Autonomous Navigation**: Give Xenon a task (like "Apply to this job" or "Extract the top 5 trending posts"), and it will autonomously navigate, click, type, and extract data.
- **Strict Tab Isolation**: Xenon is strictly locked to the tab you invoke it on, preventing it from wandering into unrelated background tabs or disrupting your personal browsing.
- **Liquid UI**: A clean, minimalist Google-inspired React interface inside your Chrome side-panel.
- **WebSocket Streaming**: Real-time status updates and agent actions are streamed directly to the UI, keeping you informed at every step.
- **Tiered Fallback Engine**: If the primary LLM fails or hits rate limits, Xenon automatically falls back to secondary API keys to ensure your task completes.

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, WebSockets, `browser-use` (Playwright/CDP)
- **Frontend (Extension)**: React, Vite, CSS (Minimalist Flat White)
- **AI Models**: Google Gemini (`gemini-3.1-flash-lite`, `gemini-3.5-flash`), DeepSeek via NVIDIA NIM

## 📦 Setup & Installation

### 1. Backend Setup
Navigate to the `backend` directory, install dependencies, and run the server.

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Start the WebSocket server
uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Extension Setup
Navigate to the `extension` directory and build the React app.

```bash
cd extension
npm install
npm run build
```

Once built, open Chrome and navigate to `chrome://extensions/`. Turn on **Developer mode** and click **Load unpacked**. Select the `extension/dist` folder to install the Xenon extension.

### 3. Chrome Debugging Setup
Xenon connects to your live Chrome instance using the Chrome DevTools Protocol (CDP). You must launch Chrome with remote debugging enabled.

Run the provided batch script to launch a dedicated Chrome instance:
```bash
Launch_Chrome.bat
```
*(This launches Chrome with `--remote-debugging-port=9222`)*

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
