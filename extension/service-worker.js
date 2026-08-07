chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error('Panel behavior setup error:', error));

chrome.action.onClicked.addListener((tab) => {
});

console.log('Browser Use service worker started');