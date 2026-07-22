console.log("Background script loaded");

// Open the panel at window level (NOT tab-level) so it stays open when the tab navigates
// openPanelOnActionClick: true opens per-tab — Chrome closes it on navigation. We handle it manually.
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: false })
  .catch((error) => console.error("setPanelBehavior error:", error));

// When user clicks the extension icon, open the panel for the WINDOW (not the tab)
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ windowId: tab.windowId }).catch((e) => console.error("sidePanel.open error:", e));
});

chrome.sidePanel.setOptions({
  path: 'index.html',
  enabled: true
}).catch((error) => console.error("setOptions error:", error));


let isServerStarted = false;

function startServer() {
  if (isServerStarted) return;
  try {
    console.log("Attempting to start Xenon backend server via Native Messaging...");
    const port = chrome.runtime.connectNative('com.xenon.server');
    
    port.onMessage.addListener((response) => {
      console.log("Native Host Response:", response);
      isServerStarted = true;
      port.disconnect();
    });

    port.onDisconnect.addListener(() => {
      if (chrome.runtime.lastError) {
        console.warn("Native Messaging Error:", chrome.runtime.lastError.message);
      }
    });

    port.postMessage({ action: "start_server" });
  } catch (e) {
    console.error("Failed to start native messaging:", e);
  }
}

// Try to start immediately when Service Worker boots
startServer();

let isAgentRunning = false;

function updateEdgeLighting() {
  chrome.tabs.query({}, (tabs) => {
    tabs.forEach(tab => {
      if (tab.url && (tab.url.startsWith('chrome://') || tab.url.startsWith('edge://'))) return;
      
      const shouldShowHere = isAgentRunning && tab.active;
      
      const cssCode = `
        @keyframes xenon-breathe {
          0%, 100% { 
            background-color: rgba(0, 210, 255, 0.005);
            box-shadow: 
              inset 0 0 2px 1px rgba(0, 210, 255, 0.4), 
              inset 0 0 15px rgba(0, 210, 255, 0.2), 
              inset 0 0 40px rgba(0, 210, 255, 0.05); 
          }
          50% { 
            background-color: rgba(0, 210, 255, 0.02);
            box-shadow: 
              inset 0 0 4px 2px rgba(0, 210, 255, 0.5), 
              inset 0 0 25px rgba(0, 210, 255, 0.4), 
              inset 0 0 70px rgba(0, 210, 255, 0.1); 
          }
        }
        #xenon-agent-comet-border {
          position: fixed;
          top: 0; left: 0; width: 100vw; height: 100vh;
          pointer-events: none;
          z-index: 2147483647;
          box-sizing: border-box;
          border: none;
          animation: xenon-breathe 2.5s infinite ease-in-out;
        }
      `;

      if (shouldShowHere) {
        chrome.scripting.insertCSS({
          target: { tabId: tab.id },
          css: cssCode
        }).catch(() => {});
        
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => {
            if (document.getElementById('xenon-agent-comet-border')) return;
            const container = document.createElement('div');
            container.id = 'xenon-agent-comet-border';
            if (document.body) document.body.appendChild(container);
            else document.documentElement.appendChild(container);
          }
        }).catch(() => {});
      } else {
        chrome.scripting.removeCSS({
          target: { tabId: tab.id },
          css: cssCode
        }).catch(() => {});
        
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => {
            const container = document.getElementById('xenon-agent-comet-border');
            if (container) container.remove();
          }
        }).catch(() => {});
      }
    });
  });
}

chrome.tabs.onActivated.addListener(() => {
  if (isAgentRunning) updateEdgeLighting();
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (isAgentRunning && changeInfo.status === 'complete') {
    updateEdgeLighting();
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'start_server_if_needed') {
    startServer();
    sendResponse({ ok: true });
    return true;
  }
  if (message.action === 'toggleEdgeLighting') {
    isAgentRunning = message.shouldShow;
    updateEdgeLighting();
  }
});
