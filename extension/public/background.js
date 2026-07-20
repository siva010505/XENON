console.log("Background script loaded");
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .then(() => console.log("Side panel behavior set"))
  .catch((error) => console.error(error));
