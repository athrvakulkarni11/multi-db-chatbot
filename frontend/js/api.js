/**
 * NeuroChat — API Client
 */

const API_BASE = '/api';

const api = {
    // --- Chat ---
    async sendMessage(message, conversationId = null) {
        const response = await fetch(`${API_BASE}/chat/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, conversation_id: conversationId })
        });
        if (!response.ok) throw new Error(`Chat error: ${response.statusText}`);
        return response.json();
    },

    async streamMessage(message, conversationId = null, onChunk, onDone) {
        const response = await fetch(`${API_BASE}/chat/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, conversation_id: conversationId })
        });
        if (!response.ok) throw new Error(`Chat stream error: ${response.statusText}`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.type === 'chunk') {
                            onChunk(data);
                        } else if (data.type === 'done') {
                            if (onDone) onDone(data);
                        }
                    } catch (e) {
                        console.error('Parse error:', e);
                    }
                }
            }
        }
    },

    async getConversations() {
        const response = await fetch(`${API_BASE}/chat/conversations`);
        if (!response.ok) throw new Error('Failed to load conversations');
        return response.json();
    },

    async getConversation(id) {
        const response = await fetch(`${API_BASE}/chat/conversations/${id}`);
        if (!response.ok) throw new Error('Failed to load conversation');
        return response.json();
    },

    async deleteConversation(id) {
        const response = await fetch(`${API_BASE}/chat/conversations/${id}`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Failed to delete conversation');
        return response.json();
    },

    async renameConversation(id, title) {
        const response = await fetch(`${API_BASE}/chat/conversations/${id}?title=${encodeURIComponent(title)}`, {
            method: 'PATCH'
        });
        if (!response.ok) throw new Error('Failed to rename conversation');
        return response.json();
    },

    // --- Memory ---
    async getMemories(type = null, limit = 50) {
        const params = new URLSearchParams();
        if (type && type !== 'all') params.set('memory_type', type);
        params.set('limit', limit);
        const response = await fetch(`${API_BASE}/memories/?${params}`);
        if (!response.ok) throw new Error('Failed to load memories');
        return response.json();
    },

    async createMemory(content, type = 'semantic', importance = 0.5, tags = []) {
        const response = await fetch(`${API_BASE}/memories/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                content,
                memory_type: type,
                importance,
                tags
            })
        });
        if (!response.ok) throw new Error('Failed to create memory');
        return response.json();
    },

    async searchMemories(query, topK = 5, type = null) {
        const body = { query, top_k: topK };
        if (type && type !== 'all') body.memory_type = type;
        const response = await fetch(`${API_BASE}/memories/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        if (!response.ok) throw new Error('Failed to search memories');
        return response.json();
    },

    async deleteMemory(id) {
        const response = await fetch(`${API_BASE}/memories/${id}`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Failed to delete memory');
        return response.json();
    },

    async getMemoryStats() {
        const response = await fetch(`${API_BASE}/memories/stats`);
        if (!response.ok) throw new Error('Failed to load memory stats');
        return response.json();
    },

    // --- Documents ---
    async getDocuments() {
        const response = await fetch(`${API_BASE}/documents/`);
        if (!response.ok) throw new Error('Failed to load documents');
        return response.json();
    },

    async uploadDocument(file) {
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch(`${API_BASE}/documents/upload`, {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }
        return response.json();
    },

    async getDocument(id) {
        const response = await fetch(`${API_BASE}/documents/${id}`);
        if (!response.ok) throw new Error('Failed to load document');
        return response.json();
    },

    async deleteDocument(id) {
        const response = await fetch(`${API_BASE}/documents/${id}`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Failed to delete document');
        return response.json();
    },

    async searchDocuments(query, topK = 5) {
        const response = await fetch(`${API_BASE}/documents/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, top_k: topK })
        });
        if (!response.ok) throw new Error('Failed to search documents');
        return response.json();
    },

    // --- Analytics ---
    async getAnalyticsOverview() {
        const response = await fetch(`${API_BASE}/analytics/overview`);
        if (!response.ok) throw new Error('Failed to load analytics');
        return response.json();
    },

    async getSearchStats() {
        const response = await fetch(`${API_BASE}/analytics/search-stats`);
        if (!response.ok) throw new Error('Failed to load search stats');
        return response.json();
    },

    // --- Advanced Features ---
    async getKnowledgeGraph() {
        const response = await fetch(`${API_BASE}/advanced/knowledge-graph`);
        if (!response.ok) throw new Error('Failed to load knowledge graph');
        return response.json();
    },

    async buildKnowledgeGraph() {
        const response = await fetch(`${API_BASE}/advanced/knowledge-graph/build`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to build knowledge graph');
        return response.json();
    },

    async analyzeSentiment(text) {
        const response = await fetch(`${API_BASE}/advanced/sentiment/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        if (!response.ok) throw new Error('Sentiment analysis failed');
        return response.json();
    },

    async getConversationSentiment(conversationId) {
        const response = await fetch(`${API_BASE}/advanced/sentiment/conversation`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ conversation_id: conversationId })
        });
        if (!response.ok) throw new Error('Failed to get sentiment');
        return response.json();
    },

    async clusterTopics(nClusters = 5) {
        const response = await fetch(`${API_BASE}/advanced/topics/cluster`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ n_clusters: nClusters })
        });
        if (!response.ok) throw new Error('Clustering failed');
        return response.json();
    },

    async getFollowUpSuggestions(userMessage, assistantResponse) {
        const response = await fetch(`${API_BASE}/advanced/suggestions/followup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_message: userMessage,
                assistant_response: assistantResponse
            })
        });
        if (!response.ok) throw new Error('Failed to get suggestions');
        return response.json();
    },

    async summarizeDocument(text, filename = 'document') {
        const response = await fetch(`${API_BASE}/advanced/summarize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, filename })
        });
        if (!response.ok) throw new Error('Summarization failed');
        return response.json();
    },

    async exportConversation(conversationId, format = 'markdown') {
        const response = await fetch(`${API_BASE}/advanced/export/${conversationId}/${format}`);
        if (!response.ok) throw new Error('Export failed');
        if (format === 'json') return response.json();
        return response.text();
    },

    // --- Health ---
    async checkHealth() {
        try {
            const response = await fetch(`${API_BASE}/health`);
            if (!response.ok) return { status: 'error' };
            return response.json();
        } catch {
            return { status: 'disconnected' };
        }
    }
};
