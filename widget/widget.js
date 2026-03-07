(function () {
    const scriptTag = document.currentScript;
    const API_URL = scriptTag ? scriptTag.getAttribute('data-api-url') : 'http://localhost:8000';
    let chatHistory = JSON.parse(localStorage.getItem('quarked_chat_history') || '[]');

    // 1. Inject KaTeX dependencies if not already loaded
    if (!document.getElementById('qk-katex-css')) {
        const katexCss = document.createElement('link');
        katexCss.id = 'qk-katex-css';
        katexCss.rel = 'stylesheet';
        katexCss.href = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css';
        document.head.appendChild(katexCss);
    }

    if (!document.getElementById('qk-katex-js')) {
        const katexJs = document.createElement('script');
        katexJs.id = 'qk-katex-js';
        katexJs.src = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js';
        document.head.appendChild(katexJs);
    }

    // Inject auto-render extension to easily parse the text content
    if (!document.getElementById('qk-katex-auto-render')) {
        const katexRender = document.createElement('script');
        katexRender.id = 'qk-katex-auto-render';
        katexRender.src = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js';
        document.head.appendChild(katexRender);
    }

    // 2. Inject Scoped CSS into the document
    const style = document.createElement('style');
    style.innerHTML = `
        .qk-widget-container {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 9999;
            font-family: 'Syne', sans-serif;
            box-sizing: border-box;
        }

        .qk-widget-container * {
            box-sizing: border-box;
        }

        /* Floating Button */
        .qk-launcher {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background-color: #f0c674;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(240, 198, 116, 0.4);
            transition: transform 0.3s ease;
        }

        .qk-launcher:hover {
            transform: scale(1.05);
        }

        .qk-launcher svg {
            width: 30px;
            height: 30px;
            fill: #0a0a0a;
        }

        /* Chat Panel */
        .qk-panel {
            position: absolute;
            bottom: 80px;
            right: 0;
            width: 400px;
            height: 600px;
            background-color: #0a0a0a;
            border: 1px solid #2a2a2a;
            border-radius: 1rem;
            display: none;
            flex-direction: column;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            /* animation */
            transform-origin: bottom right;
            transform: scale(0.95);
            opacity: 0;
            transition: all 0.3s ease;
        }

        .qk-panel.qk-open {
            display: flex;
            transform: scale(1);
            opacity: 1;
        }

        /* Subtle Grain Overlay inside panel (pseudo element) */
        .qk-panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
            opacity: 0.03;
            pointer-events: none;
            z-index: 0;
        }

        /* Header */
        .qk-header {
            padding: 16px;
            background-color: #111111;
            border-bottom: 1px solid #2a2a2a;
            display: flex;
            flex-direction: column;
            gap: 12px;
            position: relative;
            z-index: 1;
        }
        
        .qk-header-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .qk-title {
            font-family: 'Instrument Serif', serif;
            font-size: 1.5rem;
            font-style: italic;
            color: #f0c674;
            margin: 0;
        }

        .qk-close-btn {
            background: none;
            border: none;
            color: #a0a0a0;
            cursor: pointer;
            font-size: 1.5rem;
            padding: 0;
            line-height: 1;
            transition: color 0.2s;
        }

        .qk-close-btn:hover {
            color: #f0c674;
        }

        .qk-filters {
            display: flex;
            gap: 8px;
        }

        .qk-select {
            background-color: #161616;
            color: #ffffff;
            border: 1px solid #2a2a2a;
            border-radius: 4px;
            padding: 6px;
            font-size: 0.8rem;
            font-family: 'Syne', sans-serif;
            outline: none;
            flex: 1;
        }

        /* Messages Area */
        .qk-messages {
            flex: 1;
            padding: 16px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 16px;
            background-color: #111111;
            position: relative;
            z-index: 1;
        }

        .qk-msg {
            max-width: 85%;
            padding: 12px 16px;
            border-radius: 0.75rem;
            font-size: 0.95rem;
            line-height: 1.5;
            word-wrap: break-word;
        }

        .qk-msg-user {
            align-self: flex-end;
            background-color: #f0c674;
            color: #0a0a0a;
            border-bottom-right-radius: 4px;
        }

        .qk-msg-ai {
            align-self: flex-start;
            background-color: #161616;
            color: #ffffff;
            border: 1px solid #2a2a2a;
            border-bottom-left-radius: 4px;
        }

        /* Message Formatting elements */
        .qk-msg.qk-msg-ai strong { color: #f0c674; font-weight: 700; }
        .qk-msg.qk-msg-ai em { font-style: italic; color: #d4a84a; }

        /* Quick Actions */
        .qk-actions {
            padding: 8px 16px;
            display: flex;
            gap: 8px;
            border-top: 1px solid #2a2a2a;
            background-color: #111111;
            position: relative;
            z-index: 1;
            overflow-x: auto;
            white-space: nowrap;
        }

        .qk-action-btn {
            background-color: #161616;
            color: #a0a0a0;
            border: 1px solid #2a2a2a;
            border-radius: 1rem;
            padding: 6px 12px;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s;
            font-family: 'Syne', sans-serif;
        }

        .qk-action-btn:hover {
            color: #f0c674;
            border-color: #f0c674;
        }

        /* Input Area */
        .qk-input-area {
            padding: 16px;
            background-color: #0a0a0a;
            border-top: 1px solid #2a2a2a;
            display: flex;
            gap: 8px;
            position: relative;
            z-index: 1;
        }

        .qk-textarea {
            flex: 1;
            background-color: #161616;
            color: #ffffff;
            border: 1px solid #2a2a2a;
            border-radius: 0.5rem;
            padding: 10px 12px;
            font-family: 'Syne', sans-serif;
            resize: none;
            height: 44px;
            max-height: 120px;
            outline: none;
        }
        
        .qk-textarea:focus { border-color: #d4a84a; }

        .qk-send-btn {
            background-color: #f0c674;
            color: #0a0a0a;
            border: none;
            border-radius: 0.5rem;
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: background-color 0.2s;
        }

        .qk-send-btn:disabled {
            background-color: #444;
            cursor: not-allowed;
        }

        .qk-send-btn svg {
            width: 20px;
            height: 20px;
            fill: currentColor;
        }

        .qk-footer {
            text-align: center;
            padding: 6px 0 12px;
            font-size: 0.7rem;
            color: #666;
            background: #0a0a0a;
            position: relative;
            z-index: 1;
        }

        /* Typing Indicator */
        .qk-typing {
            display: flex;
            gap: 4px;
            align-items: center;
            padding: 16px;
        }
        .qk-typing-dot {
            width: 6px;
            height: 6px;
            background-color: #a0a0a0;
            border-radius: 50%;
            animation: qk-bounce 1.4s infinite ease-in-out both;
        }
        .qk-typing-dot:nth-child(1) { animation-delay: -0.32s; }
        .qk-typing-dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes qk-bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }

        /* Mobile specific styles */
        @media (max-width: 768px) {
            .qk-panel {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                border-radius: 0;
                bottom: 0;
            }
        }
    `;
    document.head.appendChild(style);

    // 3. Create the HTML Structure
    const widgetContainer = document.createElement('div');
    widgetContainer.className = 'qk-widget-container';

    const initialValues = {
        subject: localStorage.getItem('qk_subject') || 'Mathematics',
        board: localStorage.getItem('qk_board') || 'IGCSE',
        level: localStorage.getItem('qk_level') || 'Extended'
    };

    widgetContainer.innerHTML = `
        <div class="qk-panel" id="qk-chat-panel">
            <div class="qk-header">
                <div class="qk-header-top">
                    <h3 class="qk-title">Quarked AI Tutor</h3>
                    <button class="qk-close-btn" id="qk-close-btn">&times;</button>
                </div>
                <div class="qk-filters">
                    <select class="qk-select" id="qk-subject-select">
                        <option value="Physics" ${initialValues.subject === 'Physics' ? 'selected' : ''}>Physics</option>
                        <option value="Mathematics" ${initialValues.subject === 'Mathematics' ? 'selected' : ''}>Mathematics</option>
                        <option value="Chemistry" ${initialValues.subject === 'Chemistry' ? 'selected' : ''}>Chemistry</option>
                        <option value="Economics" ${initialValues.subject === 'Economics' ? 'selected' : ''}>Economics</option>
                        <option value="Computer Science" ${initialValues.subject === 'Computer Science' ? 'selected' : ''}>Computer Science</option>
                        <option value="ICT" ${initialValues.subject === 'ICT' ? 'selected' : ''}>ICT</option>
                    </select>
                    <select class="qk-select" id="qk-board-select">
                        <option value="IGCSE" ${initialValues.board === 'IGCSE' ? 'selected' : ''}>IGCSE</option>
                        <option value="IB" ${initialValues.board === 'IB' ? 'selected' : ''}>IB</option>
                        <option value="A Level" ${initialValues.board === 'A Level' ? 'selected' : ''}>A Level</option>
                    </select>
                    <select class="qk-select" id="qk-level-select">
                        <!-- Populated dynamically based on board -->
                    </select>
                </div>
            </div>
            
            <div class="qk-messages" id="qk-messages">
                <!-- Messages will appear here -->
            </div>
            
            <div class="qk-actions">
                <button class="qk-action-btn" id="qk-gen-btn">Practice Question</button>
                <button class="qk-action-btn" id="qk-mark-btn" title="Paste answer to mark!">Mark Answer</button>
                <!-- Add clear chat for convenience -->
                <button class="qk-action-btn" id="qk-clear-btn" style="margin-left:auto;">Clear</button>
            </div>
            
            <div class="qk-input-area">
                <textarea class="qk-textarea" id="qk-input" placeholder="Ask your tutor..." rows="1"></textarea>
                <button class="qk-send-btn" id="qk-send-btn" disabled>
                    <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                </button>
            </div>
            <div class="qk-footer">Powered by Quarked &times; Gemini</div>
        </div>
        
        <div class="qk-launcher" id="qk-launcher">
            <svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>
        </div>
    `;

    document.body.appendChild(widgetContainer);

    // 4. Logic & Interactions
    const launcher = document.getElementById('qk-launcher');
    const panel = document.getElementById('qk-chat-panel');
    const closeBtn = document.getElementById('qk-close-btn');
    const messagesEl = document.getElementById('qk-messages');
    const inputEl = document.getElementById('qk-input');
    const sendBtn = document.getElementById('qk-send-btn');
    const subjectSelect = document.getElementById('qk-subject-select');
    const boardSelect = document.getElementById('qk-board-select');
    const levelSelect = document.getElementById('qk-level-select');

    // Select dropdown dynamics
    function updateLevelOptions() {
        const board = boardSelect.value;
        const currentLevel = initialValues.level || levelSelect.value;
        levelSelect.innerHTML = '';
        if (board === 'IGCSE') {
            levelSelect.innerHTML = `<option value="Extended">Extended</option><option value="Core">Core</option>`;
        } else if (board === 'IB') {
            levelSelect.innerHTML = `<option value="HL">HL</option><option value="SL">SL</option>`;
        } else {
            levelSelect.innerHTML = `<option value="AS Level">AS Level</option><option value="A2 Level">A2 Level</option>`;
        }
        // Attempt to re-select if exists
        Array.from(levelSelect.options).forEach(opt => {
            if (opt.value === currentLevel) opt.selected = true;
        });

        savePreferences();
    }

    function savePreferences() {
        localStorage.setItem('qk_subject', subjectSelect.value);
        localStorage.setItem('qk_board', boardSelect.value);
        localStorage.setItem('qk_level', levelSelect.value);
    }

    boardSelect.addEventListener('change', updateLevelOptions);
    subjectSelect.addEventListener('change', savePreferences);
    levelSelect.addEventListener('change', savePreferences);
    updateLevelOptions();

    // Panel Toggle
    function togglePanel() {
        const isOpen = panel.classList.contains('qk-open');
        if (isOpen) {
            panel.classList.remove('qk-open');
            setTimeout(() => { panel.style.display = 'none'; }, 300);
        } else {
            panel.style.display = 'flex';
            // slight delay to allow display flex to apply before transforming opacity
            setTimeout(() => { panel.classList.add('qk-open'); }, 10);
            scrollToBottom();
        }
    }

    launcher.addEventListener('click', togglePanel);
    closeBtn.addEventListener('click', togglePanel);

    // Format utility for simple markdown replacement before KaTeX
    function formatMessageText(text) {
        // Replace bold **text**
        let html = text.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
        // Replace italic *text*
        html = html.replace(/\\*(.*?)\\*/g, '<em>$1</em>');
        // Re-encode newlines to br
        html = html.replace(/\\n/g, '<br/>');
        return html;
    }

    // Render Messages
    function renderMessages() {
        messagesEl.innerHTML = '';
        chatHistory.forEach(msg => {
            const div = document.createElement('div');
            div.className = 'qk-msg ' + (msg.role === 'user' ? 'qk-msg-user' : 'qk-msg-ai');
            div.innerHTML = formatMessageText(msg.content);
            messagesEl.appendChild(div);
        });
        triggerKaTeXRender();
        scrollToBottom();
    }

    function triggerKaTeXRender() {
        if (window.renderMathInElement) {
            window.renderMathInElement(messagesEl, {
                delimiters: [
                    { left: '$$', right: '$$', display: true },
                    { left: '$', right: '$', display: false },
                    { left: '\\\\(', right: '\\\\)', display: false },
                    { left: '\\\\[', right: '\\\\]', display: true }
                ]
            });
        }
    }

    function scrollToBottom() {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    // Basic markdown parsing
    renderMessages();

    // Input handlers
    inputEl.addEventListener('input', () => {
        sendBtn.disabled = inputEl.value.trim().length === 0;
        inputEl.style.height = '44px';
        inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
    });

    inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Manage clear 
    document.getElementById('qk-clear-btn').addEventListener('click', () => {
        chatHistory = [];
        localStorage.setItem('quarked_chat_history', JSON.stringify([]));
        renderMessages();
    });

    // Send Message Logic via SSE
    async function sendMessage() {
        const text = inputEl.value.trim();
        if (!text) return;

        // Reset input
        inputEl.value = '';
        inputEl.style.height = '44px';
        sendBtn.disabled = true;

        // Add user msg
        chatHistory.push({ role: 'user', content: text });
        renderMessages();

        // Setup payload mapping to ChatRequest from FastAPI
        const payload = {
            messages: chatHistory,
            subject: subjectSelect.value,
            exam_board: boardSelect.value,
            level: levelSelect.value
            // student_id could be passed if authenticated
        };

        // Add dummy AI message for streaming
        const aiMsgIndex = chatHistory.length;
        chatHistory.push({ role: 'assistant', content: '' });

        const typingEl = document.createElement('div');
        typingEl.className = 'qk-typing qk-msg qk-msg-ai';
        typingEl.innerHTML = '<div class="qk-typing-dot"></div><div class="qk-typing-dot"></div><div class="qk-typing-dot"></div>';
        messagesEl.appendChild(typingEl);
        scrollToBottom();

        try {
            const response = await fetch(`${API_URL}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let assistantResponseText = '';

            messagesEl.removeChild(typingEl);

            // Create target div for streaming
            const streamingDiv = document.createElement('div');
            streamingDiv.className = 'qk-msg qk-msg-ai';
            messagesEl.appendChild(streamingDiv);

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\\n\\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.substring(6);
                        try {
                            const data = JSON.parse(dataStr);
                            if (data.error) {
                                console.error('Tutor error:', data.error);
                            } else if (data.text) {
                                assistantResponseText += data.text;
                                streamingDiv.innerHTML = formatMessageText(assistantResponseText);
                                scrollToBottom();
                            } else if (data.done) {
                                // stream finished
                                chatHistory[aiMsgIndex].content = assistantResponseText;
                                localStorage.setItem('quarked_chat_history', JSON.stringify(chatHistory));
                                triggerKaTeXRender();
                            }
                        } catch (e) {
                            console.error("Parse error on stream chunk", e);
                        }
                    }
                }
            }

        } catch (err) {
            console.error(err);
            chatHistory[aiMsgIndex].content = "Sorry, I had trouble connecting. Please try again.";
            localStorage.setItem('quarked_chat_history', JSON.stringify(chatHistory));
            renderMessages();
        } finally {
            sendBtn.disabled = false;
        }
    }

    sendBtn.addEventListener('click', sendMessage);

    // Quick Handlers for special backend actions could be configured similarly
    // e.g. pressing "Practice Question" inserts a hidden prompt and uses the normal chat,
    // or calls the custom /api/generate endpoint directly.
    document.getElementById('qk-gen-btn').addEventListener('click', async () => {
        // Using chat standard sequence with a targeted prompt to yield native dialogue feeling in MVP
        inputEl.value = `Generate a practice question for me on ${subjectSelect.value} for ${boardSelect.value} ${levelSelect.value}. Make it challenging!`;
        sendBtn.disabled = false;
        sendMessage();
    });

})();
