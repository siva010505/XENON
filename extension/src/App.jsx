import { useState, useEffect, useRef } from 'react';
import './index.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentAction, setCurrentAction] = useState('Analyzing');
  const [ws, setWs] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const socket = new WebSocket('ws://127.0.0.1:8000/ws/chat');

    socket.onopen = () => {
      setWs(socket);
    };

    socket.onmessage = (event) => {
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
        }
      } catch (e) {
        setMessages(prev => [...prev, { type: 'agent', text: event.data }]);
      }
    };

    socket.onclose = () => {
      setWs(null);
    };

    return () => socket.close();
  }, []);

  const sendTask = async (taskText) => {
    if (!taskText.trim() || !ws) return;

    setMessages(prev => [...prev, { type: 'user', text: taskText }]);
    setIsProcessing(true);
    setCurrentAction('Analyzing');

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
        <input
          type="text"
          className="chat-input"
          placeholder="Enter task..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !isProcessing && handleSend()}
          disabled={isProcessing || !ws}
        />
        {isProcessing ? (
          <button
            className="stop-button"
            onClick={handleStop}
            title="Pause Agent"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="6" y="4" width="4" height="16"></rect>
              <rect x="14" y="4" width="4" height="16"></rect>
            </svg>
          </button>
        ) : (
          <button
            className="send-button"
            onClick={handleSend}
            disabled={!input.trim() || !ws}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

export default App;
