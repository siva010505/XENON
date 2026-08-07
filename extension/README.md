# Browser Use Chrome Side Panel Extension

A Chrome side panel extension that brings browser-use automation directly into your browser, similar to Gemini's side panel.

## Features

- 🤖 **AI-powered browser automation** - Type natural language tasks, watch them execute in your active tab
- 📱 **Gemini-like side panel UI** - Clean chat interface with settings
- 🔌 **Native messaging host** - Secure communication with local browser-use Python backend
- 🎯 **Active tab targeting** - Automates the tab you're currently viewing
- ⚙️ **Configurable LLM providers** - Google, OpenAI, Anthropic, DeepSeek, Ollama, and more
- ⏸️ **Pause/Resume/Stop** - Full control over running tasks
- 💾 **Settings persistence** - API keys and preferences saved securely

## Prerequisites

1. **Chrome with remote debugging enabled**
   ```bash
   chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\ChromeDebugProfile"
   ```
   Or use the created desktop shortcut after installation.

2. **Python 3.10+** with browser-use dependencies (installed via requirements.txt)

3. **LLM API keys** for your chosen provider (Google, OpenAI, Anthropic, etc.)

## Installation

### 1. Install Native Messaging Host

Run as Administrator for system-wide install, or without for current user only:

```powershell
# Current user only
.\extension\host\install_host.ps1

# System-wide (requires Administrator)
.\extension\host\install_host.ps1 -SystemWide
```

Or use the batch file:
```cmd
extension\host\install_host.bat
```

This will:
- Register the native messaging host with Chrome
- Create a desktop shortcut "Chrome with Debugging" that launches Chrome with the required flags

### 2. Load Extension in Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (top right toggle)
3. Click **Load unpacked**
4. Select the `extension` folder (not the host folder)
5. The extension should appear with the Browser Use icon

### 3. Launch Chrome with Debugging

Use the created desktop shortcut **"Chrome with Debugging"** or run manually:
```bash
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\ChromeDebugProfile"
```

### 4. Configure Settings

1. Click the Browser Use icon in Chrome toolbar to open side panel
2. Click **Settings** (gear icon)
3. Select your **LLM Provider** (Google, OpenAI, etc.)
4. Choose **Model**
5. Enter your **API Key**
6. Verify **CDP URL** is `http://localhost:9222`
7. Adjust **Temperature** and **Max Steps** as needed

## Usage

1. **Open any website** in a tab
2. **Click the extension icon** to open the side panel
3. **Type your task** in natural language:
   - "Login to GitHub with my credentials"
   - "Extract all product prices from this page"
   - "Fill out the contact form with test data"
   - "Navigate to settings and change theme to dark"
4. **Press Enter** or click **Run**
5. **Watch the automation** happen in your active tab
6. **See live updates** in the side panel chat

## Controls

- **Run** - Start a new task
- **Pause** - Pause the running agent
- **Resume** - Continue paused agent
- **Stop** - Stop the current task
- **Clear** - Clear chat history

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Chrome Browser (--remote-debugging-port=9222)               │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────┐  │
│  │  Side Panel │◄──►│ background.js │◄──►│ Native Host    │  │
│  │  (React/JS) │    │ (Service     │    │ bridge.py      │  │
│  │             │    │  Worker)     │    │ (Python)       │  │
│  └─────────────┘    └──────────────┘    └───────┬────────┘  │
│                                                  │           │
│  ┌──────────────────────────────────────────────▼────────┐  │
│  │ CDP (port 9222) → Attach to Active Tab → browser-use  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Components

- **extension/manifest.json** - Chrome extension manifest (v3)
- **extension/background.js** - Service worker for message routing
- **extension/sidepanel.html** - Side panel UI structure
- **extension/sidepanel.js** - Side panel logic and chat handling
- **extension/host/manifest.json** - Native messaging host manifest
- **extension/host/bridge.py** - Python bridge to browser-use
- **src/browser/custom_browser.py** - Extended browser with CDP connection
- **src/browser/custom_context.py** - Context wrapper for existing tabs

## Troubleshooting

### "Native host not connected"
- Ensure Chrome is running with `--remote-debugging-port=9222`
- Check the native host is installed: `chrome://extensions/` → Details → "Native messaging host"
- Reinstall host: `.\extension\host\install_host.ps1`

### "Failed to connect to CDP"
- Verify Chrome debugging port: Open `http://localhost:9222/json/version` in browser
- Check no other process is using port 9222
- Ensure you're using the "Chrome with Debugging" shortcut

### "API key not found"
- Enter API key in side panel Settings
- Keys are stored locally (not synced)

### Extension not loading
- Reload extension in `chrome://extensions/`
- Check console for errors: Right-click side panel → Inspect → Console

## Security Notes

- API keys stored in Chrome's local storage (encrypted by Chrome)
- Native messaging host runs with your user permissions
- No external network connections except to your LLM provider
- CDP connection only to localhost:9222

## Development

### Project Structure
```
extension/
├── manifest.json          # Extension manifest
├── background.js          # Service worker
├── sidepanel.html         # Panel HTML
├── sidepanel.js           # Panel logic
├── icons/                 # Extension icons
└── host/
    ├── manifest.json      # Native host manifest
    ├── bridge.py          # Python bridge
    ├── install_host.ps1   # Windows install script
    └── install_host.bat   # Batch wrapper
```

### Testing Bridge Locally
```bash
cd extension/host
python bridge.py
# Type JSON messages manually for testing
```

## License

MIT License - See LICENSE file for details.