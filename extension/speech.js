let recognition = null;
let isRecording = false;
let silenceTimer = null;

function resetSilenceTimer() {
    if (silenceTimer) {
        clearTimeout(silenceTimer);
    }
    silenceTimer = setTimeout(() => {
        console.log('3s silence timeout reached, turning off mic automatically...');
        stopSpeech();
    }, 3000);
}

function clearSilenceTimer() {
    if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
    }
}

window.addEventListener('message', async (event) => {
    if (event.data && event.data.type === 'START_SPEECH') {
        startSpeech();
    } else if (event.data && event.data.type === 'STOP_SPEECH') {
        stopSpeech();
    }
});

async function startSpeech() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        window.parent.postMessage({ type: 'SPEECH_ERROR', error: 'not-supported' }, '*');
        return;
    }

    try {
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach(t => t.stop());
        }

        if (!recognition) {
            recognition = new SpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = navigator.language || 'en-US';

            let baseText = '';

            let talkingTimer = null;
            function notifyTalking() {
                window.parent.postMessage({ type: 'SPEECH_TALKING' }, '*');
                if (talkingTimer) clearTimeout(talkingTimer);
                talkingTimer = setTimeout(() => {
                    window.parent.postMessage({ type: 'SPEECH_SILENT' }, '*');
                }, 600);
            }

            recognition.onstart = () => {
                isRecording = true;
                window.parent.postMessage({ type: 'SPEECH_START' }, '*');
                resetSilenceTimer();
            };

            recognition.onspeechstart = () => {
                resetSilenceTimer();
                notifyTalking();
            };

            recognition.onsoundstart = () => {
                resetSilenceTimer();
                notifyTalking();
            };

            recognition.onresult = (evt) => {
                resetSilenceTimer();
                notifyTalking();
                let interimText = '';
                let finalText = '';
                for (let i = evt.resultIndex; i < evt.results.length; ++i) {
                    if (evt.results[i].isFinal) {
                        finalText += evt.results[i][0].transcript;
                    } else {
                        interimText += evt.results[i][0].transcript;
                    }
                }
                if (finalText) baseText += (baseText ? ' ' : '') + finalText;
                window.parent.postMessage({ type: 'SPEECH_RESULT', text: baseText + (interimText ? ' ' + interimText : '') }, '*');
            };

            recognition.onerror = (err) => {
                console.warn('Speech iframe error:', err.error);
                window.parent.postMessage({ type: 'SPEECH_ERROR', error: err.error }, '*');
                stopSpeech();
            };

            recognition.onend = () => {
                clearSilenceTimer();
                window.parent.postMessage({ type: 'SPEECH_END' }, '*');
                isRecording = false;
            };
        }

        recognition.start();
    } catch (err) {
        console.warn('Could not start speech recognition:', err);
        window.parent.postMessage({ type: 'SPEECH_ERROR', error: err.name || err.message }, '*');
    }
}

function stopSpeech() {
    clearSilenceTimer();
    if (recognition) {
        try { recognition.stop(); } catch (e) {}
    }
    isRecording = false;
}
