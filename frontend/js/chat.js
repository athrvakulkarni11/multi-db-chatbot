/**
 * NeuroChat — Chat UI Logic
 */

const ChatManager = {
    currentConversationId: null,
    isStreaming: false,
    lastSources: [],
    lastMemories: [],
    isRecording: false,
    recognition: null,

    init() {
        this.bindEvents();
        this.loadConversations();
    },

    bindEvents() {
        const chatInput = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-btn');
        const newChatBtn = document.getElementById('new-chat-btn');
        const contextBtn = document.getElementById('chat-context-btn');
        const closeContext = document.getElementById('close-context');

        chatInput.addEventListener('input', () => {
            autoResizeTextarea(chatInput);
            sendBtn.disabled = !chatInput.value.trim();
        });

        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        sendBtn.addEventListener('click', () => this.sendMessage());
        newChatBtn.addEventListener('click', () => this.newConversation());
        contextBtn.addEventListener('click', () => this.toggleContextPanel());
        closeContext.addEventListener('click', () => this.toggleContextPanel(false));

        // Voice input
        const voiceBtn = document.getElementById('voice-btn');
        if (voiceBtn) {
            voiceBtn.addEventListener('click', () => this.toggleVoiceInput());
        }

        // Export buttons
        const exportMdBtn = document.getElementById('export-md-btn');
        const exportJsonBtn = document.getElementById('export-json-btn');
        if (exportMdBtn) exportMdBtn.addEventListener('click', () => this.exportConversation('markdown'));
        if (exportJsonBtn) exportJsonBtn.addEventListener('click', () => this.exportConversation('json'));

        // Init speech recognition
        this.initVoiceRecognition();
    },

    initVoiceRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) return;

        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';

        this.recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map(result => result[0].transcript).join('');
            document.getElementById('chat-input').value = transcript;
            document.getElementById('send-btn').disabled = !transcript.trim();
        };

        this.recognition.onend = () => {
            this.isRecording = false;
            const voiceBtn = document.getElementById('voice-btn');
            if (voiceBtn) voiceBtn.classList.remove('recording');
        };

        this.recognition.onerror = () => {
            this.isRecording = false;
            const voiceBtn = document.getElementById('voice-btn');
            if (voiceBtn) voiceBtn.classList.remove('recording');
        };
    },

    toggleVoiceInput() {
        if (!this.recognition) {
            showToast('Voice input not supported in this browser', 'warning');
            return;
        }
        const voiceBtn = document.getElementById('voice-btn');
        if (this.isRecording) {
            this.recognition.stop();
            this.isRecording = false;
            voiceBtn.classList.remove('recording');
        } else {
            this.recognition.start();
            this.isRecording = true;
            voiceBtn.classList.add('recording');
            showToast('Listening...', 'info', 1500);
        }
    },

    async sendMessage() {
        const chatInput = document.getElementById('chat-input');
        const message = chatInput.value.trim();
        if (!message || this.isStreaming) return;

        // Hide welcome screen
        const welcome = document.getElementById('welcome-screen');
        if (welcome) welcome.style.display = 'none';

        // Add user message
        this.addMessage('user', message);

        // Clear input
        chatInput.value = '';
        chatInput.style.height = 'auto';
        document.getElementById('send-btn').disabled = true;

        // Show typing indicator
        this.showTypingIndicator();
        this.isStreaming = true;

        try {
            // Use streaming
            let assistantMsgEl = null;
            let fullResponse = '';

            await api.streamMessage(
                message,
                this.currentConversationId,
                // On chunk
                (data) => {
                    if (!this.currentConversationId) {
                        this.currentConversationId = data.conversation_id;
                    }
                    if (!assistantMsgEl) {
                        this.hideTypingIndicator();
                        assistantMsgEl = this.addMessage('assistant', '', true);
                    }
                    fullResponse += data.content;
                    const bubble = assistantMsgEl.querySelector('.message-content-text');
                    bubble.innerHTML = markdownToHtml(fullResponse);
                    this.scrollToBottom();
                },
                // On done
                (data) => {
                    this.currentConversationId = data.conversation_id;
                    this.lastSources = data.sources || [];
                    this.lastMemories = data.memories_used || [];

                    // Add sources if any
                    if (assistantMsgEl && this.lastSources.length > 0) {
                        this.addSourcesToMessage(assistantMsgEl, this.lastSources);
                    }

                    // Show follow-up suggestions
                    if (data.suggestions && data.suggestions.length > 0) {
                        this.showSuggestions(data.suggestions);
                    }

                    // Update context panel
                    this.updateContextPanel(this.lastMemories, this.lastSources);

                    // Refresh conversation list
                    this.loadConversations();
                }
            );
        } catch (error) {
            this.hideTypingIndicator();
            console.error('Chat error:', error);

            // Fallback to non-streaming
            try {
                const result = await api.sendMessage(message, this.currentConversationId);
                this.addMessage('assistant', result.message);
                this.currentConversationId = result.conversation_id;
                this.lastSources = result.sources || [];
                this.lastMemories = result.memories_used || [];

                if (this.lastSources.length > 0) {
                    const msgs = document.querySelectorAll('.message.assistant');
                    const lastMsg = msgs[msgs.length - 1];
                    if (lastMsg) this.addSourcesToMessage(lastMsg, this.lastSources);
                }

                this.updateContextPanel(this.lastMemories, this.lastSources);
                this.loadConversations();
            } catch (err) {
                this.addMessage('assistant', '⚠️ Failed to get response. Make sure the backend and Ollama are running.');
                showToast('Connection error. Check that the backend is running.', 'error');
            }
        } finally {
            this.isStreaming = false;
        }
    },

    addMessage(role, content, isStreaming = false) {
        const messagesEl = document.getElementById('messages');
        const div = document.createElement('div');
        div.className = `message ${role}`;

        const avatar = role === 'assistant' ? 'NC' : 'U';
        const htmlContent = isStreaming ? '' : markdownToHtml(content);

        div.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-bubble">
                <div class="message-content-text">${htmlContent}</div>
                <div class="message-time">${formatDate(new Date().toISOString())}</div>
            </div>
        `;

        messagesEl.appendChild(div);
        this.scrollToBottom();
        return div;
    },

    addSourcesToMessage(msgEl, sources) {
        const bubble = msgEl.querySelector('.message-bubble');
        if (!bubble) return;

        const sourcesHtml = `
            <div class="message-sources">
                <div class="message-sources-title">Sources</div>
                ${sources.map(s => `
                    <span class="source-pill" title="${escapeHtml(s.content?.substring(0, 200) || '')}">
                        📄 ${escapeHtml(s.document_name || 'Document')}
                    </span>
                `).join('')}
            </div>
        `;
        bubble.insertAdjacentHTML('beforeend', sourcesHtml);
    },

    showTypingIndicator() {
        const messagesEl = document.getElementById('messages');
        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.id = 'typing-indicator';
        indicator.innerHTML = `
            <div class="message-avatar" style="background: var(--accent-gradient); color: white;">NC</div>
            <div class="typing-dots">
                <span></span><span></span><span></span>
            </div>
        `;
        messagesEl.appendChild(indicator);
        this.scrollToBottom();
    },

    hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
    },

    scrollToBottom() {
        const container = document.getElementById('messages-container');
        container.scrollTop = container.scrollHeight;
    },

    async loadConversations() {
        try {
            const conversations = await api.getConversations();
            const container = document.getElementById('conversations');

            if (conversations.length === 0) {
                container.innerHTML = '<p class="empty-state">No conversations yet</p>';
                return;
            }

            container.innerHTML = conversations.map(conv => `
                <div class="conversation-item ${conv.id === this.currentConversationId ? 'active' : ''}" 
                     data-id="${conv.id}">
                    <span class="conv-title">${escapeHtml(conv.title)}</span>
                    <button class="conv-delete" data-id="${conv.id}" title="Delete conversation">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3,6 5,6 21,6"/><path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2V6"/>
                        </svg>
                    </button>
                </div>
            `).join('');

            // Bind click events
            container.querySelectorAll('.conversation-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    if (e.target.closest('.conv-delete')) return;
                    this.loadConversation(item.dataset.id);
                });
            });

            container.querySelectorAll('.conv-delete').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    if (confirm('Delete this conversation?')) {
                        await api.deleteConversation(btn.dataset.id);
                        if (this.currentConversationId === btn.dataset.id) {
                            this.newConversation();
                        }
                        this.loadConversations();
                        showToast('Conversation deleted', 'success');
                    }
                });
            });
        } catch (error) {
            console.error('Failed to load conversations:', error);
        }
    },

    async loadConversation(conversationId) {
        try {
            const conv = await api.getConversation(conversationId);
            this.currentConversationId = conversationId;

            // Update header
            document.getElementById('chat-title').textContent = conv.title;
            document.getElementById('chat-subtitle').textContent = `${conv.message_count || 0} messages`;

            // Clear and populate messages
            const messagesEl = document.getElementById('messages');
            messagesEl.innerHTML = '';

            const welcome = document.getElementById('welcome-screen');
            if (welcome) welcome.style.display = 'none';

            if (conv.messages) {
                conv.messages.forEach(msg => {
                    if (msg.role === 'user' || msg.role === 'assistant') {
                        this.addMessage(msg.role, msg.content);
                    }
                });
            }

            // Update active state
            document.querySelectorAll('.conversation-item').forEach(item => {
                item.classList.toggle('active', item.dataset.id === conversationId);
            });

            this.scrollToBottom();
        } catch (error) {
            console.error('Failed to load conversation:', error);
            showToast('Failed to load conversation', 'error');
        }
    },

    newConversation() {
        this.currentConversationId = null;
        document.getElementById('chat-title').textContent = 'New Conversation';
        document.getElementById('chat-subtitle').textContent = 'Start a conversation with NeuroChat';

        const messagesEl = document.getElementById('messages');
        messagesEl.innerHTML = `
            <div id="welcome-screen" class="welcome-screen">
                <div class="welcome-icon">
                    <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="32" cy="32" r="28" stroke="url(#welcome-grad2)" stroke-width="2" opacity="0.3"/>
                        <circle cx="32" cy="32" r="20" stroke="url(#welcome-grad2)" stroke-width="2" opacity="0.5"/>
                        <circle cx="32" cy="32" r="12" stroke="url(#welcome-grad2)" stroke-width="2"/>
                        <circle cx="32" cy="32" r="4" fill="url(#welcome-grad2)"/>
                        <defs><linearGradient id="welcome-grad2" x1="8" y1="8" x2="56" y2="56"><stop stop-color="#6366f1"/><stop offset="1" stop-color="#a855f7"/></linearGradient></defs>
                    </svg>
                </div>
                <h1>Welcome to NeuroChat</h1>
                <p>An AI assistant that remembers. Ask me anything, and I'll learn from our conversations.</p>
                <div class="welcome-features">
                    <div class="welcome-feature"><div class="feature-icon">🧠</div><h3>Persistent Memory</h3><p>I remember important details across conversations</p></div>
                    <div class="welcome-feature"><div class="feature-icon">🔍</div><h3>Semantic Search</h3><p>Find answers using intelligent context retrieval</p></div>
                    <div class="welcome-feature"><div class="feature-icon">📄</div><h3>Document Q&A</h3><p>Upload documents and ask questions about them</p></div>
                </div>
            </div>
        `;

        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
        });

        this.lastSources = [];
        this.lastMemories = [];
        this.updateContextPanel([], []);
    },

    toggleContextPanel(forceState) {
        const panel = document.getElementById('context-panel');
        if (typeof forceState === 'boolean') {
            panel.classList.toggle('open', forceState);
        } else {
            panel.classList.toggle('open');
        }
    },

    updateContextPanel(memories, sources) {
        const content = document.getElementById('context-content');

        if (!memories.length && !sources.length) {
            content.innerHTML = '<p class="empty-state">No context used yet</p>';
            return;
        }

        let html = '';

        if (memories.length > 0) {
            html += '<h4 style="font-size: var(--text-sm); color: var(--text-tertiary); margin-bottom: var(--space-3);">Memories</h4>';
            memories.forEach(m => {
                html += `
                    <div class="context-item">
                        <div class="context-item-label">Memory</div>
                        <p>${escapeHtml(m.content)}</p>
                        <div class="context-item-score">Score: ${(m.score || 0).toFixed(3)}</div>
                    </div>
                `;
            });
        }

        if (sources.length > 0) {
            html += '<h4 style="font-size: var(--text-sm); color: var(--text-tertiary); margin: var(--space-4) 0 var(--space-3);">Documents</h4>';
            sources.forEach(s => {
                html += `
                    <div class="context-item">
                        <div class="context-item-label">📄 ${escapeHtml(s.document_name || 'Document')}</div>
                        <p>${escapeHtml(truncateText(s.content || '', 200))}</p>
                        <div class="context-item-score">Score: ${(s.score || 0).toFixed(3)}</div>
                    </div>
                `;
            });
        }

        content.innerHTML = html;
    },

    showSuggestions(suggestions) {
        // Remove existing suggestions
        const existing = document.getElementById('follow-up-suggestions');
        if (existing) existing.remove();

        if (!suggestions || suggestions.length === 0) return;

        const container = document.createElement('div');
        container.id = 'follow-up-suggestions';
        container.className = 'follow-up-suggestions';
        container.innerHTML = `
            <div class="suggestions-label">Try asking:</div>
            <div class="suggestion-chips">
                ${suggestions.map(s => `
                    <button class="suggestion-chip">${escapeHtml(s)}</button>
                `).join('')}
            </div>
        `;

        const messagesEl = document.getElementById('messages');
        messagesEl.appendChild(container);

        // Bind click events to send the suggestion
        container.querySelectorAll('.suggestion-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                document.getElementById('chat-input').value = chip.textContent;
                document.getElementById('send-btn').disabled = false;
                container.remove();
                this.sendMessage();
            });
        });

        this.scrollToBottom();
    },

    async exportConversation(format) {
        if (!this.currentConversationId) {
            showToast('No conversation to export', 'warning');
            return;
        }
        try {
            const data = await api.exportConversation(this.currentConversationId, format);
            const blob = new Blob(
                [format === 'json' ? JSON.stringify(data, null, 2) : data],
                { type: format === 'json' ? 'application/json' : 'text/markdown' }
            );
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `conversation.${format === 'json' ? 'json' : 'md'}`;
            a.click();
            URL.revokeObjectURL(url);
            showToast(`Exported as ${format.toUpperCase()}`, 'success');
        } catch (error) {
            showToast('Export failed', 'error');
        }
    }
};
