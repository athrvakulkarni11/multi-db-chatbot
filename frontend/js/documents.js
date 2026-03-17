/**
 * NeuroChat — Document Manager Logic
 */

const DocumentManager = {
    documents: [],

    init() {
        this.bindEvents();
    },

    bindEvents() {
        const uploadBtn = document.getElementById('upload-doc-btn');
        const fileInput = document.getElementById('file-input');
        const searchInput = document.getElementById('doc-search-input');

        uploadBtn.addEventListener('click', () => fileInput.click());

        fileInput.addEventListener('change', (e) => {
            const files = Array.from(e.target.files);
            files.forEach(file => this.uploadFile(file));
            fileInput.value = '';
        });

        searchInput.addEventListener('input', debounce(() => {
            const query = searchInput.value.trim();
            if (query.length >= 2) {
                this.searchDocuments(query);
            } else {
                document.getElementById('doc-search-results').classList.add('hidden');
            }
        }, 500));

        // Drag and drop
        const grid = document.getElementById('documents-grid');
        grid.addEventListener('dragover', (e) => {
            e.preventDefault();
            grid.style.borderColor = 'var(--accent-primary)';
        });

        grid.addEventListener('dragleave', () => {
            grid.style.borderColor = '';
        });

        grid.addEventListener('drop', (e) => {
            e.preventDefault();
            grid.style.borderColor = '';
            const files = Array.from(e.dataTransfer.files);
            files.forEach(file => this.uploadFile(file));
        });
    },

    async loadDocuments() {
        try {
            this.documents = await api.getDocuments();
            this.renderDocuments();
        } catch (error) {
            console.error('Failed to load documents:', error);
            showToast('Failed to load documents', 'error');
        }
    },

    renderDocuments() {
        const grid = document.getElementById('documents-grid');

        if (this.documents.length === 0) {
            grid.innerHTML = `
                <div class="empty-state-card" style="grid-column: 1 / -1;">
                    <div class="empty-icon">📄</div>
                    <h3>No documents yet</h3>
                    <p>Upload PDF, DOCX, TXT, MD, or CSV files to get started</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = this.documents.map(doc => `
            <div class="document-card" data-type="${doc.file_type}" data-id="${doc.id}">
                <div class="doc-card-header">
                    <span class="doc-type-badge ${doc.file_type}">${doc.file_type.toUpperCase()}</span>
                    <div class="doc-card-actions">
                        <button class="btn-icon doc-delete-btn" data-id="${doc.id}" title="Delete document">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="3,6 5,6 21,6"/><path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2V6"/>
                            </svg>
                        </button>
                    </div>
                </div>
                <h4 class="doc-card-title">${escapeHtml(doc.title || doc.filename)}</h4>
                <div class="doc-card-meta">
                    <span>${formatFileSize(doc.file_size || 0)}</span>
                    <span>${doc.chunk_count || 0} chunks</span>
                    <span>${formatDate(doc.created_at)}</span>
                </div>
                <div class="doc-card-status ${doc.is_indexed ? 'indexed' : 'pending'}">
                    <span class="doc-status-dot"></span>
                    ${doc.is_indexed ? 'Indexed & Searchable' : 'Pending Indexing'}
                </div>
            </div>
        `).join('');

        // Bind delete buttons
        grid.querySelectorAll('.doc-delete-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm('Delete this document?')) {
                    try {
                        await api.deleteDocument(btn.dataset.id);
                        showToast('Document deleted', 'success');
                        this.loadDocuments();
                    } catch (error) {
                        showToast('Failed to delete document', 'error');
                    }
                }
            });
        });
    },

    async uploadFile(file) {
        showToast(`Uploading ${file.name}...`, 'info');

        try {
            await api.uploadDocument(file);
            showToast(`${file.name} uploaded and indexed!`, 'success');
            this.loadDocuments();
        } catch (error) {
            showToast(`Failed to upload ${file.name}: ${error.message}`, 'error');
        }
    },

    async searchDocuments(query) {
        const resultsContainer = document.getElementById('doc-search-results');

        try {
            const results = await api.searchDocuments(query);

            if (results.length === 0) {
                resultsContainer.innerHTML = '<p class="empty-state">No matching documents found</p>';
                resultsContainer.classList.remove('hidden');
                return;
            }

            resultsContainer.innerHTML = results.map(r => `
                <div class="doc-search-result">
                    <div class="doc-search-result-header">
                        <span class="doc-search-result-name">📄 ${escapeHtml(r.document_name)}</span>
                        <span class="doc-search-result-score">Score: ${r.score.toFixed(3)}</span>
                    </div>
                    <div class="doc-search-result-content">${escapeHtml(truncateText(r.content, 300))}</div>
                </div>
            `).join('');

            resultsContainer.classList.remove('hidden');
        } catch (error) {
            console.error('Document search error:', error);
            showToast('Search failed', 'error');
        }
    }
};
