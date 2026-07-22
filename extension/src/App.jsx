import { useState, useEffect, useRef } from 'react';
import './index.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentAction, setCurrentAction] = useState('Analyzing');
  const [ws, setWs] = useState(null);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speechError, setSpeechError] = useState(null);
  const [scrollClass, setScrollClass] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const recognitionRef = useRef(null);
  const originalInputRef = useRef('');

  const toggleVoiceTyping = () => {
    if (isListening) {
      recognitionRef.current?.stop();
      return;
    }

    if (!('webkitSpeechRecognition' in window)) {
      alert("Voice typing is not supported in this browser.");
      return;
    }

    try {
      const recognition = new window.webkitSpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';
      recognitionRef.current = recognition;

      originalInputRef.current = input + (input.trim().length > 0 ? ' ' : '');

      let silenceTimeout;
      const resetSilenceTimeout = () => {
        clearTimeout(silenceTimeout);
        silenceTimeout = setTimeout(() => {
          if (recognitionRef.current) {
            recognitionRef.current.stop();
          }
        }, 3000);
      };

      recognition.onstart = () => {
        setIsListening(true);
        resetSilenceTimeout();
      };
      
      recognition.onspeechstart = () => {
        setIsSpeaking(true);
        resetSilenceTimeout();
      };
      
      recognition.onspeechend = () => {
        setIsSpeaking(false);
        resetSilenceTimeout();
      };

      let speakingTimeout;
      recognition.onresult = (event) => {
        setIsSpeaking(true);
        resetSilenceTimeout();
        clearTimeout(speakingTimeout);
        speakingTimeout = setTimeout(() => setIsSpeaking(false), 1000);

        let currentTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          currentTranscript += event.results[i][0].transcript;
        }
        setInput(originalInputRef.current + currentTranscript);
      };

      recognition.onerror = (e) => {
        console.error("Speech Error:", e.error);
        if (e.error !== 'no-speech') {
          setSpeechError("Error: " + e.error);
        }
        setIsListening(false);
        if (e.error === 'not-allowed') {
          alert("Microphone access is blocked in the Side Panel! Chrome requires you to grant microphone permissions to the extension first.");
        }
      };

      recognition.onend = () => {
        setIsListening(false);
        setIsSpeaking(false);
        clearTimeout(silenceTimeout);
        clearTimeout(speakingTimeout);
      };
      
      if (speechError && speechError.startsWith("Listening")) {
        setSpeechError(null);
      }
      
      recognition.start();
    } catch (err) {
      console.error(err);
      setIsListening(false);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleInputScroll = () => {
    if (!inputRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = inputRef.current;
    
    if (scrollHeight <= clientHeight + 2) {
      setScrollClass('');
      return;
    }
    
    const isAtTop = scrollTop <= 2;
    const isAtBottom = Math.ceil(scrollTop + clientHeight) >= scrollHeight - 2;

    if (isAtTop && !isAtBottom) setScrollClass('mask-bottom');
    else if (!isAtTop && isAtBottom) setScrollClass('mask-top');
    else if (!isAtTop && !isAtBottom) setScrollClass('mask-both');
    else setScrollClass('');
  };

  // Auto-scroll and auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      if (!input.trim()) {
        inputRef.current.style.height = '40px';
      } else {
        inputRef.current.style.height = 'auto'; // Reset to recalculate
        inputRef.current.style.height = inputRef.current.scrollHeight + 'px';
      }
      inputRef.current.scrollTop = inputRef.current.scrollHeight;
      handleInputScroll();
    }
  }, [input]);

  useEffect(() => {
    const focusInput = () => {
      if (inputRef.current && !isProcessing) {
        inputRef.current.focus();
      }
    };

    // Try focusing when the panel becomes visible
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        setTimeout(focusInput, 100);
      }
    };

    // Global keyboard listener: if they type anything anywhere in the panel, snap to input
    const handleGlobalKeyDown = (e) => {
      if (
        inputRef.current && 
        document.activeElement !== inputRef.current && 
        e.key.length === 1 && 
        !e.ctrlKey && !e.metaKey && !e.altKey
      ) {
        inputRef.current.focus();
      }
    };

    document.addEventListener('visibilitychange', handleVisibility);
    window.addEventListener('keydown', handleGlobalKeyDown);
    
    // Initial mount attempt
    setTimeout(focusInput, 100);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
      window.removeEventListener('keydown', handleGlobalKeyDown);
    };
  }, [isProcessing]);



  const toggleEdgeLighting = (shouldShow) => {
    if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage) {
      chrome.runtime.sendMessage({ action: 'toggleEdgeLighting', shouldShow: shouldShow }).catch(() => {});
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    let reconnectTimer;
    let socket;
    let unmounted = false;

    const connect = () => {
      if (unmounted) return;
      // Ask the background script to start the server (forces Service Worker to wake up)
      if (typeof chrome !== 'undefined' && chrome.runtime) {
        chrome.runtime.sendMessage({ action: 'start_server_if_needed' }).catch(() => {});
      }

      // Don't open a new socket if one is already connecting/open
      if (socket && (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN)) {
        return;
      }

      const currentSocket = new WebSocket('ws://127.0.0.1:8000/ws/chat');
      socket = currentSocket;

      currentSocket.onopen = () => {
        if (unmounted) { currentSocket.close(); return; }
        setWs(currentSocket);
      };

      currentSocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'status') {
            setMessages(prev => [...prev, { type: 'system', text: data.message }]);
          } else if (data.type === 'agent_update') {
            setCurrentAction(data.message);
          } else if (data.type === 'result') {
            setMessages(prev => [...prev, { type: 'agent', text: data.message }]);
          } else if (data.type === 'done') {
            setIsProcessing(false);
            setCurrentAction('Analyzing');
            toggleEdgeLighting(false);
          }
        } catch (e) {
          setMessages(prev => [...prev, { type: 'agent', text: event.data }]);
        }
      };

      currentSocket.onclose = () => {
        setWs(null);
        socket = null;
        // Reconnect after 800ms unless component is unmounting
        if (!unmounted) {
          reconnectTimer = setTimeout(connect, 800);
        }
      };

      currentSocket.onerror = () => {
        currentSocket.close();
      };
    };

    connect(); // Initial connection

    return () => {
      unmounted = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (socket) socket.close();
    };
  }, []);

  const sendTask = async (taskText) => {
    if (!taskText.trim() || !ws) return;

    setMessages(prev => [...prev, { type: 'user', text: taskText }]);
    setIsProcessing(true);
    setCurrentAction('Analyzing');
    toggleEdgeLighting(true);

    try {
      let tabUrl = "";
      let tabTitle = "";
      if (typeof chrome !== 'undefined' && chrome.tabs) {
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tabs.length > 0) {
          tabUrl = tabs[0].url;
          tabTitle = tabs[0].title;
        }
      }

      ws.send(JSON.stringify({
        task: taskText,
        tabUrl: tabUrl,
        tabTitle: tabTitle
      }));
    } catch (e) {
      console.error("Failed to get tab info:", e);
      ws.send(JSON.stringify({ task: taskText }));
    }
  };

  const handleSend = () => {
    sendTask(input);
    setInput('');
  };

  const handleStop = () => {
    if (ws) {
      ws.send(JSON.stringify({ action: "stop" }));
      setIsProcessing(false);
      setCurrentAction('Analyzing');
      toggleEdgeLighting(false);
    }
  };

  const quickActions = [
    "Summarise this page",
    "Extract page data",
    "Fill out the form"
  ];

  return (
    <div className="app-container">
      {messages.length > 0 && (
        <div className="header">
          <img src={ws ? "icon.png" : "icon_dull.png"} alt="Xenon Logo" className="logo" />
          <div className="title">Xenon</div>
          <button
            className="clear-button"
            onClick={() => window.location.reload()}
            title="Reload Xenon"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        </div>
      )}

      {messages.length === 0 ? (
        <div className="empty-state">
          <img src={ws ? "icon.png" : "icon_dull.png"} alt="Xenon" className="empty-logo" />
          <h1 className="empty-title">Xenon</h1>
          <p className="empty-subtitle">I'm your AI web automation assistant, what can i do for you?</p>

          <div className="quick-actions">
            {quickActions.map((action, idx) => (
              <button
                key={idx}
                className="quick-action-btn"
                onClick={() => sendTask(action)}
                disabled={!ws}
              >
                {action}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="chat-container">
          {messages.map((msg, index) => (
            <div key={index} className={`chat-bubble ${msg.type}`}>
              {msg.text}
            </div>
          ))}
          {isProcessing && (
            <div className="chat-bubble agent processing">
              <span className="analyzing-text">{currentAction}</span>
              <div className="typing-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}

      <div className="input-container">
        <div className="chat-input-wrapper">
          <textarea
            ref={inputRef}
            className={`chat-input ${scrollClass}`}
            placeholder="Enter task..."
            value={input}
            rows={1}
            onChange={(e) => setInput(e.target.value)}
            onScroll={handleInputScroll}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!isProcessing && ws) handleSend();
              }
            }}
            disabled={isProcessing}
            autoFocus
          />
          <div className="input-buttons">
            <button
              className={`mic-button ${isListening ? 'listening' : ''} ${isSpeaking ? 'speaking' : ''}`}
              onClick={toggleVoiceTyping}
              title={isListening ? "Stop Voice Typing" : "Start Voice Typing"}
              disabled={isProcessing || !ws}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <line className="bar bar-1" x1="4" y1="10" x2="4" y2="14"></line>
                <line className="bar bar-2" x1="9" y1="8" x2="9" y2="16"></line>
                <line className="bar bar-3" x1="14" y1="5" x2="14" y2="19"></line>
                <line className="bar bar-4" x1="19" y1="8" x2="19" y2="16"></line>
                <line className="bar bar-5" x1="24" y1="10" x2="24" y2="14"></line>
              </svg>
            </button>

            {speechError && (
              <div style={{position: 'absolute', top: '-25px', right: '10px', fontSize: '10px', color: 'red'}}>
                {speechError}
              </div>
            )}

            {isProcessing ? (
              <button
                className="stop-button"
                onClick={handleStop}
                title="Pause Agent"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="5" y="5" width="14" height="14"></rect>
                </svg>
              </button>
            ) : input.trim() ? (
              <button
                className="send-button"
                onClick={handleSend}
                disabled={!ws}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path>
                </svg>
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
