/**
 * NeuroChat — System Settings UI
 * Model switching, tools, watch folder, file memory store
 */

const SystemManager = {
    init() {
        this.bindEvents();
    },

    bindEvents() {
        const switchBtn = document.getElementById('switch-model-btn');
        const scanBtn = document.getElementById('scan-watch-btn');

        if (switchBtn) switchBtn.addEventListener('click', () => this.switchModel());
        if (scanBtn) scanBtn.addEventListener('click', () => this.scanWatchFolder());
    },

    async loadSettingsView() {
        await Promise.all([
            this.loadModels(),
            this.loadTools(),
            this.loadWatchFolder(),
            this.loadMemoryStoreStats()
        ]);
    },

    async loadModels() {
        try {
            const data = await api.getModels();
            const select = document.getElementById('model-select');
            const label = document.getElementById('current-model-label');

            select.innerHTML = data.available_models.map(m =>
                `<option value="${m}" ${m === data.current_model ? 'selected' : ''}>${m}</option>`
            ).join('');

            label.textContent = `Current: ${data.current_model}`;
        } catch (e) {
            console.error('Failed to load models:', e);
        }
    },

    async switchModel() {
        const select = document.getElementById('model-select');
        const modelName = select.value;
        if (!modelName) return;

        const btn = document.getElementById('switch-model-btn');
        btn.disabled = true;
        btn.textContent = 'Switching...';

        try {
            const result = await api.switchModel(modelName);
            document.getElementById('current-model-label').textContent = `Current: ${result.current_model}`;
            showToast(`Switched to ${result.current_model}`, result.model_ready ? 'success' : 'warning');
        } catch (e) {
            showToast('Failed to switch model', 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Switch Model';
        }
    },

    async loadTools() {
        const container = document.getElementById('tools-list');
        try {
            const data = await api.getTools();
            if (!data.tools || data.tools.length === 0) {
                container.innerHTML = '<p class="empty-state">No tools available</p>';
                return;
            }

            const toolColors = {
                'web_search': '#11b8a6' // A nice teal color for search
            };

            container.innerHTML = data.tools.map(tool => {
                const color = toolColors[tool.name] || '#64748b';
                const params = Object.entries(tool.parameters || {});
                return `
                    <div style="padding:var(--space-4);background:var(--surface-1);border-radius:var(--radius-md);border-left:3px solid ${color};">
                        <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-2);">
                            <span style="font-weight:700;font-size:var(--text-base);color:${color};">${tool.name}</span>
                            <span style="font-size:var(--text-xs);color:var(--text-muted);background:var(--surface-2);padding:2px 8px;border-radius:var(--radius-full);">plugin</span>
                        </div>
                        <p style="font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--space-2);">${tool.description}</p>
                        ${params.length ? `<div style="font-size:var(--text-xs);color:var(--text-muted);">Params: ${params.map(([k,v]) => `<code>${k}</code>`).join(', ')}</div>` : ''}
                    </div>
                `;
            }).join('');
        } catch (e) {
            container.innerHTML = '<p class="empty-state">Failed to load tools</p>';
        }
    },

    async loadWatchFolder() {
        const container = document.getElementById('watch-folder-info');
        try {
            const data = await api.getWatchFolderStatus();
            container.innerHTML = `
                <div class="memory-stats" style="margin-bottom:var(--space-4);">
                    <div class="stat-card">
                        <div class="stat-value">${data.total_files}</div>
                        <div class="stat-label">Total Files</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" style="color:var(--success);">${data.processed}</div>
                        <div class="stat-label">Processed</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" style="color:var(--warning);">${data.pending}</div>
                        <div class="stat-label">Pending</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" style="color:${data.is_running ? 'var(--success)' : 'var(--error)'};">${data.is_running ? 'Active' : 'Stopped'}</div>
                        <div class="stat-label">Status</div>
                    </div>
                </div>
                <div style="font-size:var(--text-sm);color:var(--text-tertiary);">
                    📁 Drop files into: <code style="color:var(--accent-primary);">${data.watch_dir}</code>
                </div>
                ${data.files.length ? `
                    <div style="margin-top:var(--space-4);">
                        ${data.files.map(f => `
                            <div style="display:flex;align-items:center;gap:var(--space-3);padding:var(--space-2) 0;border-bottom:1px solid var(--border-subtle);">
                                <span style="flex:1;font-size:var(--text-sm);">${f.filename}</span>
                                <span style="font-size:var(--text-xs);color:${f.processed ? 'var(--success)' : 'var(--warning)'};">${f.processed ? '✓ Indexed' : '⏳ Pending'}</span>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            `;
        } catch (e) {
            container.innerHTML = '<p class="empty-state">Failed to load watch folder status</p>';
        }
    },

    async scanWatchFolder() {
        const btn = document.getElementById('scan-watch-btn');
        btn.disabled = true;
        btn.textContent = 'Scanning...';

        try {
            const result = await api.scanWatchFolder();
            showToast(`Scanned: ${result.scanned} files processed`, 'success');
            this.loadWatchFolder();
        } catch (e) {
            showToast('Scan failed', 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Scan Now';
        }
    },

    async loadMemoryStoreStats() {
        const container = document.getElementById('file-memory-stats');
        try {
            const data = await api.getMemoryStoreStats();
            const typeEntries = Object.entries(data.by_type || {});
            container.innerHTML = `
                <div class="memory-stats" style="margin-bottom:var(--space-4);">
                    <div class="stat-card">
                        <div class="stat-value">${data.total}</div>
                        <div class="stat-label">Total Memories</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${data.total_associations || 0}</div>
                        <div class="stat-label">Associations</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${data.average_importance || 0}</div>
                        <div class="stat-label">Avg Importance</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${data.disk_size_human || '0 B'}</div>
                        <div class="stat-label">Disk Usage</div>
                    </div>
                </div>
                <div style="font-size:var(--text-sm);color:var(--text-tertiary);margin-bottom:var(--space-3);">
                    📁 Store path: <code style="color:var(--accent-primary);">${data.store_path || ''}</code>
                </div>
                ${typeEntries.length ? `
                    <div style="display:flex;gap:var(--space-3);flex-wrap:wrap;">
                        ${typeEntries.map(([type, count]) => `
                            <span style="padding:var(--space-2) var(--space-4);background:var(--surface-2);border-radius:var(--radius-full);font-size:var(--text-sm);">
                                ${type}: <strong>${count}</strong>
                            </span>
                        `).join('')}
                    </div>
                ` : ''}
            `;
        } catch (e) {
            container.innerHTML = '<p class="empty-state">Failed to load memory store stats</p>';
        }
    }
};
