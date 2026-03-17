/**
 * NeuroChat — Memory Explorer Logic
 */

const MemoryManager = {
    memories: [],
    currentFilter: 'all',

    init() {
        this.bindEvents();
    },

    bindEvents() {
        const addBtn = document.getElementById('add-memory-btn');
        const modal = document.getElementById('add-memory-modal');
        const saveBtn = document.getElementById('save-memory-btn');
        const importanceSlider = document.getElementById('memory-importance');
        const searchInput = document.getElementById('memory-search-input');

        addBtn.addEventListener('click', () => modal.classList.remove('hidden'));

        modal.querySelector('.modal-close').addEventListener('click', () => modal.classList.add('hidden'));
        modal.querySelector('.modal-cancel').addEventListener('click', () => modal.classList.add('hidden'));
        modal.querySelector('.modal-backdrop').addEventListener('click', () => modal.classList.add('hidden'));

        saveBtn.addEventListener('click', () => this.saveMemory());

        importanceSlider.addEventListener('input', () => {
            document.getElementById('importance-value').textContent = importanceSlider.value;
        });

        // Filter buttons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.currentFilter = btn.dataset.type;
                this.loadMemories();
            });
        });

        // Search
        searchInput.addEventListener('input', debounce(() => {
            const query = searchInput.value.trim();
            if (query.length >= 2) {
                this.searchMemories(query);
            } else {
                this.loadMemories();
            }
        }, 500));
    },

    async loadMemories() {
        try {
            this.memories = await api.getMemories(this.currentFilter);
            this.renderMemories();
            this.loadStats();
        } catch (error) {
            console.error('Failed to load memories:', error);
            showToast('Failed to load memories', 'error');
        }
    },

    async loadStats() {
        try {
            const stats = await api.getMemoryStats();
            document.getElementById('total-memories').textContent = stats.total || 0;
            document.getElementById('episodic-count').textContent = stats.by_type?.episodic || 0;
            document.getElementById('semantic-count').textContent = stats.by_type?.semantic || 0;
            document.getElementById('avg-importance').textContent = (stats.average_importance || 0).toFixed(2);
        } catch (error) {
            console.error('Failed to load memory stats:', error);
        }
    },

    renderMemories(memories = null) {
        const list = document.getElementById('memory-list');
        const data = memories || this.memories;

        if (!data || data.length === 0) {
            list.innerHTML = `
                <div class="empty-state-card">
                    <div class="empty-icon">🧠</div>
                    <h3>No memories yet</h3>
                    <p>Start chatting and I'll automatically remember important details</p>
                </div>
            `;
            return;
        }

        list.innerHTML = data.map(mem => {
            const tags = typeof mem.tags === 'string' ? JSON.parse(mem.tags || '[]') : (mem.tags || []);
            const importance = mem.importance || 0;
            const impClass = importance > 0.7 ? 'high' : importance > 0.4 ? 'medium' : 'low';

            return `
                <div class="memory-item" data-type="${mem.memory_type}" data-id="${mem.id}">
                    <div class="memory-item-header">
                        <span class="memory-type-badge ${mem.memory_type}">${mem.memory_type}</span>
                        <div class="memory-item-actions">
                            ${mem.score !== undefined && mem.score !== null ? `<span class="memory-score">Score: ${mem.score.toFixed(3)}</span>` : ''}
                            <button class="btn-icon memory-delete-btn" data-id="${mem.id}" title="Delete memory">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="3,6 5,6 21,6"/><path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2V6"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                    <div class="memory-item-content">${escapeHtml(mem.content)}</div>
                    <div class="memory-item-footer">
                        <div class="memory-item-meta">
                            <div class="memory-importance">
                                <span>Importance:</span>
                                <div class="importance-bar">
                                    <div class="importance-fill ${impClass}" style="width: ${importance * 100}%"></div>
                                </div>
                                <span>${importance.toFixed(1)}</span>
                            </div>
                            <span>${formatDate(mem.created_at)}</span>
                            ${mem.access_count ? `<span>Accessed ${mem.access_count}×</span>` : ''}
                        </div>
                        ${tags.length > 0 ? `
                            <div class="memory-tags">
                                ${tags.map(t => `<span class="memory-tag">${escapeHtml(t)}</span>`).join('')}
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');

        // Bind delete buttons
        list.querySelectorAll('.memory-delete-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                if (confirm('Delete this memory?')) {
                    try {
                        await api.deleteMemory(btn.dataset.id);
                        showToast('Memory deleted', 'success');
                        this.loadMemories();
                    } catch (error) {
                        showToast('Failed to delete memory', 'error');
                    }
                }
            });
        });
    },

    async saveMemory() {
        const content = document.getElementById('memory-content').value.trim();
        const type = document.getElementById('memory-type').value;
        const importance = parseFloat(document.getElementById('memory-importance').value);
        const tagsStr = document.getElementById('memory-tags').value.trim();
        const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(t => t) : [];

        if (!content) {
            showToast('Please enter memory content', 'warning');
            return;
        }

        try {
            await api.createMemory(content, type, importance, tags);
            showToast('Memory saved!', 'success');

            // Clear form and close modal
            document.getElementById('memory-content').value = '';
            document.getElementById('memory-tags').value = '';
            document.getElementById('memory-importance').value = '0.5';
            document.getElementById('importance-value').textContent = '0.5';
            document.getElementById('add-memory-modal').classList.add('hidden');

            this.loadMemories();
        } catch (error) {
            showToast('Failed to save memory', 'error');
        }
    },

    async searchMemories(query) {
        try {
            const results = await api.searchMemories(query, 10, this.currentFilter);
            this.renderMemories(results);
        } catch (error) {
            console.error('Memory search error:', error);
            showToast('Search failed', 'error');
        }
    }
};
