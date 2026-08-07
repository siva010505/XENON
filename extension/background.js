/**
 * Background Service Worker for Browser Use Side Panel Extension
 * Opens the side panel on action icon click
 */

// Set side panel behavior to open on action click
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error('Panel behavior setup error:', error));

// Handle extension action click
chrome.action.onClicked.addListener((tab) => {
  if (tab && tab.windowId) {
    chrome.sidePanel.open({ windowId: tab.windowId })
      .catch((error) => console.error('Error opening side panel:', error));
  }
});

console.log('Browser Use side panel service worker active.');