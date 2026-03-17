/**
 * NeuroChat — Main Application Controller
 */

const App = {
    currentView: 'chat',

    async init() {
        console.log('🧠 Initializing NeuroChat...');

        // Initialize modules
        ChatManager.init();
        DocumentManager.init();
        MemoryManager.init();
        AnalyticsDashboard.init();
        AdvancedManager.init();

        // Bind navigation
        this.bindNavigation();

        // Bind sidebar toggle
        this.bindSidebarToggle();

        // Check backend health
        this.checkHealth();

        // Periodic health check
        setInterval(() => this.checkHealth(), 30000);

        console.log('✅ NeuroChat initialized');
    },

    bindNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                const view = item.dataset.view;
                this.switchView(view);
            });
        });
    },

    switchView(view) {
        this.currentView = view;

        // Update nav items
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.view === view);
        });

        // Show/hide views
        document.querySelectorAll('.view').forEach(v => {
            v.classList.toggle('active', v.id === `view-${view}`);
        });

        // Show/hide conversation list
        const convList = document.getElementById('conversation-list');
        convList.style.display = view === 'chat' ? 'flex' : 'none';

        // Load data for the view
        this.loadViewData(view);
    },

    loadViewData(view) {
        switch (view) {
            case 'chat':
                ChatManager.loadConversations();
                break;
            case 'documents':
                DocumentManager.loadDocuments();
                break;
            case 'memory':
                MemoryManager.loadMemories();
                break;
            case 'analytics':
                AnalyticsDashboard.loadAnalytics();
                break;
            case 'knowledge':
                AdvancedManager.loadKnowledgeView();
                break;
        }
    },

    bindSidebarToggle() {
        const sidebar = document.getElementById('sidebar');
        const toggle = document.getElementById('sidebar-toggle');

        toggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
        });
    },

    async checkHealth() {
        const statusEl = document.getElementById('connection-status');
        const textEl = statusEl.querySelector('.status-text');

        try {
            const health = await api.checkHealth();

            if (health.status === 'running') {
                statusEl.className = 'connection-status connected';
                if (health.llm?.model_ready) {
                    textEl.textContent = `Connected • ${health.llm.configured_model}`;
                } else if (health.llm?.status === 'connected') {
                    textEl.textContent = 'Ollama connected • Model not found';
                } else {
                    textEl.textContent = 'API running • Ollama offline';
                    statusEl.className = 'connection-status disconnected';
                }
            } else {
                statusEl.className = 'connection-status disconnected';
                textEl.textContent = 'Backend offline';
            }
        } catch {
            statusEl.className = 'connection-status disconnected';
            textEl.textContent = 'Cannot connect';
        }
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
