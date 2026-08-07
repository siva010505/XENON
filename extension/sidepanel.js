/**
 * Browser Use Side Panel - Main JavaScript
 * Connects directly to FastAPI backend (http://localhost:7788) via REST & SSE
 */

const BACKEND_URL = 'http://localhost:7788';

// State
let currentTaskId = null;
let isConnected = false;
let isRunning = false;
let isPaused = false;
let isWaitingHelp = false;
let eventSource = null;
let settings = {};
let personalData = []; // Array of {id, key, value} stored in chrome.storage.local

// DOM Elements
const chatContainer = document.getElementById('chatContainer');
const taskInput = document.getElementById('taskInput');
const submitBtn = document.getElementById('submitBtn');
const submitBtnText = document.getElementById('submitBtnText');
const micBtn = document.getElementById('micBtn');
const clearBtn = document.getElementById('clearBtn');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const settingsToggleBtn = document.getElementById('settingsToggleBtn');
const settingsModal = document.getElementById('settingsModal');
const closeSettingsBtn = document.getElementById('closeSettingsBtn');
const welcomeMsg = document.getElementById('welcomeMsg');

// Speech Recognition State
let recognition = null;
let isRecording = false;

// Settings elements
const setProvider = document.getElementById('setProvider');
const setModel = document.getElementById('setModel');
const setApiKey = document.getElementById('setApiKey');
const setTemperature = document.getElementById('setTemperature');
const setMaxSteps = document.getElementById('setMaxSteps');
const setMaxActions = document.getElementById('setMaxActions');
const setUseVision = document.getElementById('setUseVision');

// Fallback Model options by provider
const DEFAULT_MODEL_OPTIONS = {
    google: ['gemini-3.1-flash-lite', 'gemini-2.5-computer-use-preview-10-2025', 'gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.0-flash'],
    openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1-mini', 'o3-mini'],
    anthropic: ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229'],
    nvidia: ['meta/llama-3.3-70b-instruct', 'nvidia/llama-3.1-nemotron-70b-instruct', 'deepseek-ai/deepseek-r1', 'mistralai/mistral-large-2411', 'google/gemma-2-27b-it'],
    deepseek: ['deepseek-chat', 'deepseek-reasoner'],
    ollama: ['qwen2.5:7b', 'deepseek-r1:14b', 'llama3.1:8b', 'llama3.2:3b', 'mistral:7b'],
    grok: ['grok-3', 'grok-2', 'grok-1'],
    mistral: ['mistral-large-latest', 'mistral-medium', 'mistral-small', 'pixtral-large'],
    azure_openai: ['gpt-4o', 'gpt-4-turbo', 'gpt-35-turbo'],
    bedrock: ['anthropic.claude-3-5-sonnet', 'anthropic.claude-3-opus', 'meta.llama3-70b'],
    vertex_ai: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.0-flash'],
};

let serverModels = {};

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await loadSettings();
    await loadPersonalData();
    setupEventListeners();
    setupSpeechRecognition();
    await checkConnection();
    await fetchBackendSettings();
    updateModelOptions();
    connectSSE();
    setInterval(checkConnection, 3000);
});

// Setup Speech Recognition via Embedded Iframe Bridge
function setupSpeechRecognition() {
    const btn = document.getElementById('micBtn');
    const speechIframe = document.getElementById('speechIframe');
    if (!btn || !speechIframe) return;

    window.addEventListener('message', (event) => {
        if (!event.data) return;
        if (event.data.type === 'SPEECH_START') {
            isRecording = true;
            btn.classList.add('recording');
            btn.title = 'Stop listening';
        } else if (event.data.type === 'SPEECH_TALKING') {
            btn.classList.add('talking');
        } else if (event.data.type === 'SPEECH_SILENT') {
            btn.classList.remove('talking');
        } else if (event.data.type === 'SPEECH_RESULT') {
            if (event.data.text !== undefined) {
                taskInput.value = event.data.text;
                taskInput.style.height = 'auto';
                taskInput.style.height = Math.min(taskInput.scrollHeight, 100) + 'px';
                updateSendButtonVisibility();
            }
        } else if (event.data.type === 'SPEECH_END' || event.data.type === 'SPEECH_ERROR') {
            isRecording = false;
            btn.classList.remove('recording');
            btn.classList.remove('talking');
            btn.title = 'Voice typing';
            if (event.data.type === 'SPEECH_ERROR') {
                const errStr = String(event.data.error || '');
                if (errStr.includes('not-allowed') || errStr.includes('NotAllowedError') || errStr.includes('PermissionDeniedError')) {
                    addMessage('assistant', `⚠️ **Microphone Access Required**: Please grant microphone permission in Chrome for this extension.`);
                }
            }
        }
    });

    btn.addEventListener('click', () => {
        if (!speechIframe.contentWindow) return;
        if (isRecording) {
            speechIframe.contentWindow.postMessage({ type: 'STOP_SPEECH' }, '*');
        } else {
            speechIframe.contentWindow.postMessage({ type: 'START_SPEECH' }, '*');
        }
    });
}

function stopSpeechRecognition() {
    isRecording = false;
    const btn = document.getElementById('micBtn');
    const speechIframe = document.getElementById('speechIframe');
    if (btn) {
        btn.classList.remove('recording');
        btn.title = 'Voice typing';
    }
    if (speechIframe && speechIframe.contentWindow) {
        try {
            speechIframe.contentWindow.postMessage({ type: 'STOP_SPEECH' }, '*');
        } catch (e) {}
    }
}

// Load settings from chrome.storage
async function loadSettings() {
    return new Promise((resolve) => {
        chrome.storage.sync.get([
            'provider', 'model', 'temperature', 'maxSteps', 'maxActions', 'useVision'
        ], (items) => {
            settings = {
                provider: items.provider || 'google',
                model: items.model || 'gemini-3.1-flash-lite',
                apiKey: '',
                cdpUrl: 'http://localhost:9222',
                temperature: items.temperature !== undefined ? items.temperature : 0.6,
                maxSteps: items.maxSteps || 100,
                maxActions: items.maxActions || 1,
                useVision: items.useVision !== false,
                keepOpen: true,
            };
            
            chrome.storage.local.get(['apiKey'], (localItems) => {
                settings.apiKey = localItems.apiKey || '';
                applySettingsToUI();
                resolve();
            });
        });
    });
}

// Save settings to chrome.storage
async function saveSettings() {
    const syncItems = {
        provider: settings.provider,
        model: settings.model,
        temperature: settings.temperature,
        maxSteps: settings.maxSteps,
        maxActions: settings.maxActions,
        useVision: settings.useVision,
    };
    
    const localItems = {
        apiKey: settings.apiKey,
    };
    
    return new Promise((resolve) => {
        chrome.storage.sync.set(syncItems, () => {
            chrome.storage.local.set(localItems, resolve);
        });
    });
}

// Apply settings to UI elements
function applySettingsToUI() {
    setProvider.value = settings.provider || 'google';
    const tempNum = (settings.temperature !== undefined && settings.temperature !== null) ? parseFloat(settings.temperature) : 0.6;
    const tempStr = tempNum.toFixed(1);
    setTemperature.value = tempStr;
    if (!setTemperature.value) {
        setTemperature.value = '0.6';
    }
    setMaxSteps.value = settings.maxSteps || 100;
    setMaxActions.value = settings.maxActions || 1;
    setUseVision.checked = settings.useVision !== false;
    setApiKey.value = settings.apiKey || '';
    setModel.value = settings.model || 'gemini-3.1-flash-lite';
}

// Fetch available models/providers from FastAPI backend
async function fetchBackendSettings() {
    try {
        const res = await fetch(`${BACKEND_URL}/api/settings`);
        if (res.ok) {
            const data = await res.json();
            if (data.providers) {
                serverModels = data.providers;
                updateModelOptions();
            }
        }
    } catch (e) {
        console.warn('Could not fetch backend settings:', e);
    }
}

// Update model options dropdown based on provider
function updateModelOptions() {
    const provider = setProvider.value;
    const models = serverModels[provider] || DEFAULT_MODEL_OPTIONS[provider] || [];
    
    const modelDatalist = document.getElementById('modelOptions');
    if (!modelDatalist) return;
    
    modelDatalist.innerHTML = '';
    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        modelDatalist.appendChild(option);
    });
}

// ---- Personal Autofill Data: Load, Save, Render ----

async function loadPersonalData() {
    return new Promise((resolve) => {
        chrome.storage.local.get(['personalData'], (items) => {
            personalData = Array.isArray(items.personalData) ? items.personalData : [];
            renderPersonalData();
            resolve();
        });
    });
}

async function savePersonalData() {
    return new Promise((resolve) => {
        chrome.storage.local.set({ personalData }, resolve);
    });
}

function renderPersonalData() {
    const list = document.getElementById('personalDataList');
    if (!list) return;
    list.innerHTML = '';

    // Update count badge and nav sub-text
    const countBadge = document.getElementById('personalInfoCount');
    const navSub = document.getElementById('personalInfoNavSub');
    const count = personalData.length;
    if (countBadge) countBadge.textContent = count === 0 ? '0 saved' : `${count} saved`;
    if (navSub) navSub.textContent = count === 0 ? 'Manage your saved details' : `${count} detail${count === 1 ? '' : 's'} saved`;

    if (count === 0) {
        list.innerHTML = '<div class="personal-data-empty">No personal info saved yet.</div>';
        return;
    }

    personalData.forEach((entry) => {
        const row = document.createElement('div');
        row.className = 'personal-data-entry';
        row.dataset.id = entry.id;
        row.innerHTML = `
            <span class="personal-data-entry-key" title="${entry.key}">${entry.key}</span>
            <span class="personal-data-entry-sep">:</span>
            <span class="personal-data-entry-value" title="${entry.value}">${entry.value}</span>
            <button class="personal-data-delete-btn" title="Remove" data-id="${entry.id}">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        `;
        row.querySelector('.personal-data-delete-btn').addEventListener('click', async () => {
            personalData = personalData.filter(e => e.id !== entry.id);
            await savePersonalData();
            renderPersonalData();
        });
        list.appendChild(row);
    });
}

// ---- Settings Sub-page Navigation ----
function showSettingsPage(page) {
    const mainPage = document.getElementById('settingsPageMain');
    const personalPage = document.getElementById('settingsPagePersonal');
    if (!mainPage || !personalPage) return;

    if (page === 'personal') {
        mainPage.classList.add('page-hidden-right');
        personalPage.classList.remove('page-hidden-right');
        // Ensure modal-pages height tracks the personal page
        const pagesEl = document.getElementById('modalPages');
        if (pagesEl) pagesEl.style.minHeight = personalPage.scrollHeight + 'px';
    } else {
        personalPage.classList.add('page-hidden-right');
        mainPage.classList.remove('page-hidden-right');
        const pagesEl = document.getElementById('modalPages');
        if (pagesEl) pagesEl.style.minHeight = '';
    }
}

// Setup Event Listeners
function setupEventListeners() {
    submitBtn.addEventListener('click', handleSubmit);
    taskInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    });
    
    taskInput.addEventListener('input', () => {
        taskInput.style.height = 'auto';
        taskInput.style.height = Math.min(taskInput.scrollHeight, 62) + 'px';
        updateSendButtonVisibility();
    });
    
    clearBtn.addEventListener('click', clearChat);

    settingsToggleBtn.addEventListener('click', () => {
        // Always reset to main settings page when opening
        showSettingsPage('main');
        settingsModal.classList.add('open');
    });

    closeSettingsBtn.addEventListener('click', () => {
        settingsModal.classList.remove('open');
        showSettingsPage('main');
    });

    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            settingsModal.classList.remove('open');
            showSettingsPage('main');
        }
    });

    // Personal Info sub-page navigation
    const goToPersonalInfoBtn = document.getElementById('goToPersonalInfoBtn');
    const backToSettingsBtn = document.getElementById('backToSettingsBtn');
    if (goToPersonalInfoBtn) {
        goToPersonalInfoBtn.addEventListener('click', () => showSettingsPage('personal'));
    }
    if (backToSettingsBtn) {
        backToSettingsBtn.addEventListener('click', () => showSettingsPage('main'));
    }


    setProvider.addEventListener('change', () => {
        settings.provider = setProvider.value;
        updateModelOptions();
        saveSettings();
    });
    
    setModel.addEventListener('change', () => {
        settings.model = setModel.value;
        saveSettings();
    });
    
    setApiKey.addEventListener('change', () => {
        settings.apiKey = setApiKey.value;
        saveSettings();
    });
    
    setTemperature.addEventListener('change', () => {
        settings.temperature = parseFloat(setTemperature.value);
        saveSettings();
    });
    
    setMaxSteps.addEventListener('change', () => {
        settings.maxSteps = parseInt(setMaxSteps.value);
        saveSettings();
    });

    setMaxActions.addEventListener('change', () => {
        settings.maxActions = parseInt(setMaxActions.value) || 1;
        saveSettings();
    });
    
    setUseVision.addEventListener('change', () => {
        settings.useVision = setUseVision.checked;
        saveSettings();
    });

    // Personal Autofill Data: Add button
    const addPersonalDataBtn = document.getElementById('addPersonalDataBtn');
    const newDataKey = document.getElementById('newDataKey');
    const newDataValue = document.getElementById('newDataValue');
    if (addPersonalDataBtn && newDataKey && newDataValue) {
        const doAdd = async () => {
            const k = newDataKey.value.trim();
            const v = newDataValue.value.trim();
            if (!k || !v) return;
            personalData.push({ id: Date.now().toString(), key: k, value: v });
            await savePersonalData();
            renderPersonalData();
            newDataKey.value = '';
            newDataValue.value = '';
            newDataKey.focus();
        };
        addPersonalDataBtn.addEventListener('click', doAdd);
        newDataValue.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); doAdd(); }
        });
    }

    document.querySelectorAll('.ready-btn, .ready-card').forEach(btn => {
        btn.addEventListener('click', () => {
            const prompt = btn.getAttribute('data-prompt');
            if (prompt) {
                taskInput.value = prompt;
                handleSubmit();
            }
        });
    });
}

let isStartingServer = false;
let nativeHostAttempted = false;

// Check connection to FastAPI backend
async function checkConnection() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/health`, { method: 'GET' });
        if (response.ok) {
            if (isStartingServer) {
                isStartingServer = false;
                updateStartingServerUI(false);
                await fetchBackendSettings();
                updateModelOptions();
                connectSSE();
            }
            updateConnectionStatus(true);
            return true;
        } else {
            handleOfflineConnection();
            return false;
        }
    } catch {
        handleOfflineConnection();
        return false;
    }
}

function handleOfflineConnection() {
    updateConnectionStatus(false);
    if (!nativeHostAttempted && typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendNativeMessage) {
        nativeHostAttempted = true;
        isStartingServer = true;
        updateStartingServerUI(true);
        
        try {
            chrome.runtime.sendNativeMessage('com.xenon.server', { action: 'start' }, (response) => {
                const err = chrome.runtime.lastError;
                if (err) {
                    console.warn('Native messaging host response:', err.message);
                } else {
                    console.log('Native messaging host triggered:', response);
                }
            });
        } catch (e) {
            console.warn('Could not trigger Native Messaging Host:', e);
        }
        
        // Poll every 1 second until server starts up
        const pollTimer = setInterval(async () => {
            const online = await checkConnection();
            if (online) {
                clearInterval(pollTimer);
            }
        }, 1000);
    }
}

function updateStartingServerUI(starting) {
    const logoImg = document.querySelector('.hero-logo-img');
    if (logoImg) {
        if (starting) {
            logoImg.classList.add('starting');
            logoImg.classList.remove('disconnected');
        } else {
            logoImg.classList.remove('starting');
        }
    }
    if (starting) {
        taskInput.placeholder = 'Booting Xenon...';
    } else {
        taskInput.placeholder = 'Enter task...';
    }
}

function updateConnectionStatus(connected) {
    isConnected = connected;
    const logoImg = document.querySelector('.hero-logo-img');
    const readyCards = document.querySelectorAll('.ready-card');
    
    if (logoImg) {
        if (connected) {
            logoImg.classList.remove('disconnected');
            logoImg.classList.remove('starting');
        } else if (!isStartingServer) {
            logoImg.classList.add('disconnected');
        }
    }
    
    readyCards.forEach(card => {
        if (connected) {
            card.classList.remove('disabled');
        } else {
            card.classList.add('disabled');
        }
    });
    
    submitBtn.disabled = !connected;
    taskInput.disabled = !connected || isRunning;
    const micBtn = document.getElementById('micBtn');
    if (micBtn) micBtn.disabled = !connected || isRunning;
}

// Connect to Server-Sent Events (SSE) stream
function connectSSE() {
    if (eventSource) {
        eventSource.close();
    }
    
    try {
        eventSource = new EventSource(`${BACKEND_URL}/api/stream`);
        
        eventSource.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                handleStreamMessage(message);
            } catch (e) {
                console.error('Failed to parse SSE event:', e);
            }
        };
        
        eventSource.onerror = () => {
            console.warn('SSE connection error, retrying in 3s...');
            setTimeout(connectSSE, 3000);
        };
    } catch (e) {
        console.error('Error creating EventSource:', e);
    }
}

// Handle incoming SSE messages
function handleStreamMessage(msg) {
    if (!msg || !msg.type) return;
    
    switch (msg.type) {
        case 'status':
            handleStatusEvent(msg.data);
            break;
        case 'step':
            handleStepEvent(msg.data);
            break;
        case 'done':
            handleDoneEvent(msg.data);
            break;
        case 'ask_user':
            handleAskUserEvent(msg.data);
            break;
        case 'error':
            handleErrorEvent(msg.data);
            break;
    }
}

function handleStatusEvent(status) {
    console.log('Status change:', status);
    if (status === 'initializing' || status === 'running') {
        isRunning = true;
        isPaused = false;
        isWaitingHelp = false;
        setStatus('running', status === 'initializing' ? 'Initializing...' : 'Executing...');
        setControlsState(true);
    } else if (status === 'paused') {
        isPaused = true;
        setStatus('paused', 'Paused');
    } else if (status === 'waiting_help') {
        isWaitingHelp = true;
        setStatus('paused', 'Needs Input');
        submitBtn.className = 'btn btn-primary';
        submitBtn.disabled = false;
        submitBtnText.textContent = 'Submit Answer';
        taskInput.disabled = false;
        taskInput.placeholder = 'Provide response for agent...';
    } else if (status === 'done' || status === 'stopped') {
        finishActiveStepsContainer(status === 'stopped' ? 'Stopped' : 'Completed');
        isRunning = false;
        isPaused = false;
        isWaitingHelp = false;
        setStatus('idle', 'Task Done');
        setControlsState(false);
    } else if (status === 'error') {
        finishActiveStepsContainer('Failed');
        isRunning = false;
        isPaused = false;
        isWaitingHelp = false;
        setStatus('error', 'Error');
        setControlsState(false);
    }
}

let activeStepsWrapper = null;
let activeStepsBody = null;
let activeStepsCountLabel = null;
let activeStepsBadge = null;
let activeStepsCount = 0;
let taskStartTime = null;

function createStepsContainer() {
    if (welcomeMsg) {
        welcomeMsg.style.display = 'none';
    }
    
    activeStepsCount = 0;
    taskStartTime = Date.now();

    const assistantGroup = document.createElement('div');
    assistantGroup.className = 'message assistant steps-group';
    assistantGroup.innerHTML = `<div class="message-label">Xenon</div>`;

    const wrapper = document.createElement('div');
    wrapper.className = 'steps-container-wrapper open';
    
    wrapper.innerHTML = `
        <div class="steps-main-header">
            <div class="steps-header-title">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="9 18 15 12 9 6"></polyline>
                </svg>
                <span class="steps-count-label">Working<span class="loading-dots"><span>.</span><span>.</span><span>.</span></span></span>
            </div>
            <span class="steps-badge running" style="display:none;">Working...</span>
        </div>
        <div class="steps-main-body"></div>
    `;
    
    const header = wrapper.querySelector('.steps-main-header');
    header.addEventListener('click', () => {
        wrapper.classList.toggle('open');
    });
    
    activeStepsWrapper = wrapper;
    activeStepsBody = wrapper.querySelector('.steps-main-body');
    activeStepsCountLabel = wrapper.querySelector('.steps-count-label');
    activeStepsBadge = wrapper.querySelector('.steps-badge');
    
    assistantGroup.appendChild(wrapper);
    chatContainer.appendChild(assistantGroup);
    scrollToBottom();
    return wrapper;
}

function finishActiveStepsContainer(statusText = 'Completed') {
    if (activeStepsWrapper) {
        if (activeStepsCountLabel) {
            if ((statusText === 'Completed' || statusText === 'Stopped') && taskStartTime) {
                const elapsedSec = Math.round((Date.now() - taskStartTime) / 1000);
                let timeStr = '';
                if (elapsedSec < 60) {
                    timeStr = `${elapsedSec} sec`;
                } else {
                    const mins = Math.floor(elapsedSec / 60);
                    const secs = elapsedSec % 60;
                    timeStr = secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
                }
                activeStepsCountLabel.textContent = `Worked for ${timeStr}`;
            } else {
                activeStepsCountLabel.textContent = `Steps (${activeStepsCount})`;
            }
        }
        if (activeStepsBadge) {
            activeStepsBadge.className = 'steps-badge';
            activeStepsBadge.textContent = statusText;
        }
        // Collapse outer steps container cleanly after completion
        activeStepsWrapper.classList.remove('open');
        // Collapse all individual step items inside
        if (activeStepsBody) {
            const allItems = activeStepsBody.querySelectorAll('.step-item');
            allItems.forEach(item => item.classList.remove('open'));
        }
        activeStepsWrapper = null;
        activeStepsBody = null;
        activeStepsCountLabel = null;
        activeStepsBadge = null;
    }
}

function handleStepEvent(stepData) {
    if (!stepData) return;
    const stepNum = stepData.step;
    const output = stepData.output || '';
    
    if (!activeStepsWrapper || !chatContainer.contains(activeStepsWrapper)) {
        createStepsContainer();
    }
    
    let stepItem = activeStepsBody.querySelector(`#step-item-${stepNum}`);
    let isNew = false;
    if (!stepItem) {
        isNew = true;
        stepItem = document.createElement('div');
        stepItem.id = `step-item-${stepNum}`;
        stepItem.className = 'step-item';
        
        stepItem.innerHTML = `
            <div class="step-item-header">
                <div class="step-item-title">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                    <span>Step ${stepNum}</span>
                </div>
            </div>
            <div class="step-item-body"></div>
        `;
        
        const itemHeader = stepItem.querySelector('.step-item-header');
        itemHeader.addEventListener('click', () => {
            stepItem.classList.toggle('open');
        });
        
        activeStepsBody.appendChild(stepItem);
        activeStepsCount++;
    }
    
    const stepBody = stepItem.querySelector('.step-item-body');
    stepBody.innerHTML = formatMarkdown(output);
    
    // Automatically collapse previous steps and expand the newest step while running
    if (isNew) {
        const allItems = activeStepsBody.querySelectorAll('.step-item');
        allItems.forEach(item => item.classList.remove('open'));
        stepItem.classList.add('open');
    }
    
    scrollToBottom();
}

function cleanSummaryText(text) {
    if (!text) return '';
    let cleaned = text;
    // Strip header like ### 🎉 Task Completed or ### Task Completed
    cleaned = cleaned.replace(/^###\s*(🎉)?\s*\*?\*?Task Completed\*?\*?\s*/gi, '');
    // Strip **Result:** or Result:
    cleaned = cleaned.replace(/^\s*\*?\*?Result:\*?\*?\s*/gi, '');
    // Strip bottom Duration / Steps / Errors footers
    cleaned = cleaned.replace(/⏱️\s*\*?\*?Duration:\*?\*?[\s\S]*$/gi, '');
    cleaned = cleaned.replace(/🔢\s*\*?\*?Steps:\*?\*?[\s\S]*$/gi, '');
    cleaned = cleaned.replace(/⚠️\s*\*?\*?Errors Encountered:\*?\*?[\s\S]*$/gi, '');
    return cleaned.trim();
}

function createErrorContainer(errorText) {
    if (!errorText) return;
    const str = String(errorText).trim();
    if (!str || str === 'null' || str === 'undefined' || str === 'None' || str === '[]') return;

    const wrapper = document.createElement('div');
    wrapper.className = 'error-container-wrapper'; // Closed by default!
    
    wrapper.innerHTML = `
        <div class="error-main-header">
            <div class="error-header-title">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="9 18 15 12 9 6"></polyline>
                </svg>
                <span>Errors Encountered</span>
            </div>
        </div>
        <div class="error-main-body">
            <pre style="white-space: pre-wrap; font-family: inherit; margin: 0; font-size: 11.5px;">${formatMarkdown(str)}</pre>
        </div>
    `;
    
    const header = wrapper.querySelector('.error-main-header');
    header.addEventListener('click', () => {
        wrapper.classList.toggle('open');
    });
    
    chatContainer.appendChild(wrapper);
    scrollToBottom();
}

function handleDoneEvent(data) {
    const hasStepsGroup = !!activeStepsWrapper;
    finishActiveStepsContainer('Completed');
    let summary = data?.summary || 'Task completed successfully.';
    summary = cleanSummaryText(summary);
    addMessage('assistant', summary, { skipLabel: hasStepsGroup });

    if (data?.errors) {
        createErrorContainer(data.errors);
    }

    setStatus('idle', 'Task Done');
    setControlsState(false);
}

function handleAskUserEvent(data) {
    const query = data?.query || 'Agent requires input';
    addMessage('assistant', `❓ **Agent Question:** ${query}\n\n*Type your response in the input box below and click Submit Answer.*`);
}

function handleErrorEvent(errorMsg) {
    finishActiveStepsContainer('Failed');
    addMessage('assistant', 'An error occurred during execution.');
    createErrorContainer(errorMsg);
    setStatus('error', 'Error');
    setControlsState(false);
}

// Submit Task or User Response or Stop Task
async function handleSubmit() {
    stopSpeechRecognition();
    if (isWaitingHelp) {
        // Submit help response
        const text = taskInput.value.trim();
        if (!text) return;
        taskInput.value = '';
        taskInput.style.height = 'auto';
        try {
            await fetch(`${BACKEND_URL}/api/help-response`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ response: text })
            });
        } catch (e) {
            addMessage('assistant', `❌ Error submitting response: ${e.message}`);
        }
        return;
    }
    
    if (isRunning) {
        // Run button clicked while task is running -> STOP task!
        await handleStop();
        return;
    }
    
    const text = taskInput.value.trim();
    if (!text) return;
    
    // Start new task
    taskInput.value = '';
    taskInput.style.height = 'auto';
    addMessage('user', text);
    createStepsContainer();
    
    // Get current active tab URL to attach automation to exact tab
    let targetUrl = null;
    try {
        if (typeof chrome !== 'undefined' && chrome.tabs) {
            const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (activeTab && activeTab.url) {
                targetUrl = activeTab.url;
            }
        }
    } catch (tabErr) {
        console.warn('Could not query active tab URL:', tabErr);
    }
    
    const payload = {
        task: text,
        provider: settings.provider,
        model: settings.model,
        apiKey: settings.apiKey,
        cdpUrl: settings.cdpUrl || 'http://localhost:9222',
        targetUrl: targetUrl,
        temperature: settings.temperature,
        maxSteps: settings.maxSteps,
        maxActions: settings.maxActions || 1,
        useVision: settings.useVision,
        keepOpen: true,
        personalData: personalData.length > 0 ? personalData : [],
    };
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/run-task`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Failed to start task');
        }
        
        const data = await response.json();
        currentTaskId = data.task_id;
    } catch (e) {
        addMessage('assistant', `❌ **Failed to start task**: ${e.message}`);
        setStatus('error', 'Error');
        setControlsState(false);
    }
}

// Stop Agent
async function handleStop() {
    try {
        await fetch(`${BACKEND_URL}/api/stop`, { method: 'POST' });
        setStatus('idle', 'Stopping...');
    } catch (e) {
        console.error('Stop failed:', e);
    }
}

// Render Messages & Screenshots
function addMessage(role, content, options = {}) {
    if (welcomeMsg) {
        welcomeMsg.style.display = 'none';
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const label = role === 'user' ? 'You' : 'Xenon';
    const showLabel = !options.skipLabel;
    
    messageDiv.innerHTML = `
        ${showLabel ? `<div class="message-label">${label}</div>` : ''}
        <div class="message-content">${formatMarkdown(content)}</div>
    `;
    
    chatContainer.appendChild(messageDiv);
    scrollToBottom();
    return messageDiv;
}

function clearChat() {
    chatContainer.innerHTML = '';
    welcomeMsg.style.display = 'flex';
    chatContainer.appendChild(welcomeMsg);
    currentTaskId = null;
    activeStepsWrapper = null;
    activeStepsBody = null;
    activeStepsCountLabel = null;
    activeStepsBadge = null;
    activeStepsCount = 0;
    setStatus('idle', 'Ready');
    setControlsState(false);
}

function setStatus(status, text) {
    updateConnectionStatus(isConnected);
}

function updateSendButtonVisibility() {
    const hasText = taskInput.value.trim().length > 0;
    if (hasText || isRunning) {
        submitBtn.style.display = 'flex';
    } else {
        submitBtn.style.display = 'none';
    }
}

function setControlsState(running) {
    isRunning = running;
    submitBtn.disabled = !isConnected;
    const micBtn = document.getElementById('micBtn');
    if (micBtn) micBtn.disabled = !isConnected || running;

    if (running) {
        submitBtn.className = 'btn-action-circle btn-send-whatsapp running';
        submitBtn.title = 'Stop task';
        submitBtn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <rect x="5" y="5" width="14" height="14" rx="2" />
            </svg>
        `;
        taskInput.disabled = true;
        taskInput.placeholder = 'Task is running...';
    } else {
        submitBtn.className = 'btn-action-circle btn-send-whatsapp';
        submitBtn.title = 'Send task';
        submitBtn.innerHTML = `
            <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
        `;
        taskInput.disabled = !isConnected;
        taskInput.placeholder = 'Enter task...';
    }
    updateSendButtonVisibility();
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function formatMarkdown(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>');
}

window.addEventListener('focus', () => {
    checkConnection();
});