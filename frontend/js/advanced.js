/**
 * NeuroChat — Advanced Features UI
 * Knowledge Graph, Topic Clusters, Sentiment
 */

const AdvancedManager = {
    graphData: null,
    animationFrame: null,
    nodes: [],

    init() {
        this.bindEvents();
    },

    bindEvents() {
        const buildBtn = document.getElementById('build-graph-btn');
        const clusterBtn = document.getElementById('cluster-btn');

        if (buildBtn) buildBtn.addEventListener('click', () => this.buildKnowledgeGraph());
        if (clusterBtn) clusterBtn.addEventListener('click', () => this.clusterMemories());
    },

    async loadKnowledgeView() {
        // Try to load existing graph
        try {
            this.graphData = await api.getKnowledgeGraph();
            if (this.graphData.nodes && this.graphData.nodes.length > 0) {
                this.renderGraph(this.graphData);
            }
        } catch (e) {
            // No graph yet, that's fine
        }
    },

    async buildKnowledgeGraph() {
        const btn = document.getElementById('build-graph-btn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Building...';
        showToast('Building knowledge graph from memories...', 'info');

        try {
            const result = await api.buildKnowledgeGraph();
            this.graphData = result.graph;
            this.renderGraph(this.graphData);
            showToast(`Graph built: ${result.nodes} entities, ${result.edges} relationships`, 'success');
        } catch (error) {
            showToast('Failed to build knowledge graph', 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23,4 23,10 17,10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg> Build Graph`;
        }
    },

    renderGraph(data) {
        const canvas = document.getElementById('kg-canvas');
        const container = document.getElementById('kg-container');
        const emptyMsg = document.getElementById('kg-empty');
        const ctx = canvas.getContext('2d');

        if (!data.nodes || data.nodes.length === 0) {
            if (emptyMsg) emptyMsg.style.display = 'flex';
            return;
        }
        if (emptyMsg) emptyMsg.style.display = 'none';

        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;

        const width = canvas.width;
        const height = canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;

        // Type colors
        const typeColors = {
            'PERSON': '#6366f1',
            'PLACE': '#22c55e',
            'ORG': '#f59e0b',
            'CONCEPT': '#a855f7',
            'TECH': '#3b82f6',
            'EVENT': '#ef4444',
            'OTHER': '#64748b'
        };

        // Position nodes in a force-directed-like layout
        const nodes = data.nodes.map((node, i) => {
            const angle = (i / data.nodes.length) * Math.PI * 2;
            const radius = Math.min(width, height) * 0.33;
            // Add some randomness for organic feel
            const jitterX = (Math.random() - 0.5) * 60;
            const jitterY = (Math.random() - 0.5) * 60;
            return {
                ...node,
                x: centerX + Math.cos(angle) * radius + jitterX,
                y: centerY + Math.sin(angle) * radius + jitterY,
                vx: 0,
                vy: 0,
                radius: Math.max(18, Math.min(35, 15 + (node.count || 1) * 5))
            };
        });

        // Simple force simulation (a few steps)
        const nodeMap = {};
        nodes.forEach(n => nodeMap[n.id] = n);

        for (let iter = 0; iter < 50; iter++) {
            // Repulsion between all nodes
            for (let i = 0; i < nodes.length; i++) {
                for (let j = i + 1; j < nodes.length; j++) {
                    const dx = nodes[j].x - nodes[i].x;
                    const dy = nodes[j].y - nodes[i].y;
                    const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
                    const force = 800 / (dist * dist);
                    const fx = (dx / dist) * force;
                    const fy = (dy / dist) * force;
                    nodes[i].vx -= fx;
                    nodes[i].vy -= fy;
                    nodes[j].vx += fx;
                    nodes[j].vy += fy;
                }
            }

            // Attraction along edges
            for (const edge of (data.edges || [])) {
                const source = nodeMap[edge.source];
                const target = nodeMap[edge.target];
                if (!source || !target) continue;
                const dx = target.x - source.x;
                const dy = target.y - source.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                const force = (dist - 120) * 0.01;
                const fx = (dx / Math.max(1, dist)) * force;
                const fy = (dy / Math.max(1, dist)) * force;
                source.vx += fx;
                source.vy += fy;
                target.vx -= fx;
                target.vy -= fy;
            }

            // Center gravity
            for (const node of nodes) {
                node.vx += (centerX - node.x) * 0.002;
                node.vy += (centerY - node.y) * 0.002;
                node.x += node.vx * 0.3;
                node.y += node.vy * 0.3;
                node.vx *= 0.8;
                node.vy *= 0.8;
                // Keep in bounds
                node.x = Math.max(node.radius + 10, Math.min(width - node.radius - 10, node.x));
                node.y = Math.max(node.radius + 10, Math.min(height - node.radius - 10, node.y));
            }
        }

        this.nodes = nodes;

        // Draw
        ctx.clearRect(0, 0, width, height);

        // Draw edges
        for (const edge of (data.edges || [])) {
            const source = nodeMap[edge.source];
            const target = nodeMap[edge.target];
            if (!source || !target) continue;

            ctx.beginPath();
            ctx.moveTo(source.x, source.y);
            ctx.lineTo(target.x, target.y);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // Edge label
            const midX = (source.x + target.x) / 2;
            const midY = (source.y + target.y) / 2;
            ctx.fillStyle = 'rgba(160, 160, 184, 0.6)';
            ctx.font = '9px Inter';
            ctx.textAlign = 'center';
            ctx.fillText(edge.relation || '', midX, midY - 4);
        }

        // Draw nodes
        for (const node of nodes) {
            const color = typeColors[node.type] || typeColors.OTHER;

            // Glow effect
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius + 4, 0, Math.PI * 2);
            ctx.fillStyle = color + '20';
            ctx.fill();

            // Node circle
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
            const gradient = ctx.createRadialGradient(
                node.x - node.radius * 0.3, node.y - node.radius * 0.3, 0,
                node.x, node.y, node.radius
            );
            gradient.addColorStop(0, color);
            gradient.addColorStop(1, color + '99');
            ctx.fillStyle = gradient;
            ctx.fill();

            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.stroke();

            // Label
            ctx.fillStyle = '#ffffff';
            ctx.font = `bold ${Math.max(9, 12 - Math.floor(node.label.length / 4))}px Inter`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            const label = node.label.length > 10 ? node.label.substring(0, 9) + '…' : node.label;
            ctx.fillText(label, node.x, node.y);

            // Type badge below
            ctx.fillStyle = 'rgba(160, 160, 184, 0.7)';
            ctx.font = '8px Inter';
            ctx.fillText(node.type, node.x, node.y + node.radius + 12);
        }

        // Legend
        let legendX = 10;
        const legendY = height - 15;
        ctx.font = '10px Inter';
        for (const [type, color] of Object.entries(typeColors)) {
            ctx.fillStyle = color;
            ctx.fillRect(legendX, legendY - 4, 8, 8);
            ctx.fillStyle = '#a0a0b8';
            ctx.textAlign = 'left';
            ctx.fillText(type, legendX + 12, legendY + 3);
            legendX += ctx.measureText(type).width + 24;
            if (legendX > width - 60) break;
        }
    },

    async clusterMemories() {
        const btn = document.getElementById('cluster-btn');
        btn.disabled = true;
        btn.textContent = 'Clustering...';

        try {
            const result = await api.clusterTopics(5);
            this.renderClusters(result.clusters);
            showToast(`Found ${result.num_clusters} topic clusters`, 'success');
        } catch (error) {
            showToast('Clustering failed', 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Cluster Memories';
        }
    },

    renderClusters(clusters) {
        const container = document.getElementById('topic-clusters');

        if (!clusters || clusters.length === 0) {
            container.innerHTML = '<p class="empty-state">No clusters found. Add more memories first.</p>';
            return;
        }

        const clusterColors = ['#6366f1', '#a855f7', '#22c55e', '#f59e0b', '#3b82f6', '#ef4444', '#14b8a6', '#ec4899'];

        container.innerHTML = clusters.map((cluster, i) => {
            const color = clusterColors[i % clusterColors.length];
            return `
                <div class="topic-cluster" style="border-left: 3px solid ${color};">
                    <div class="cluster-header" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--space-3);">
                        <div>
                            <span class="cluster-label" style="font-weight:700;font-size:var(--text-base);color:${color};">${escapeHtml(cluster.label)}</span>
                            <span style="font-size:var(--text-xs);color:var(--text-tertiary);margin-left:var(--space-2);">${cluster.count} memories</span>
                        </div>
                    </div>
                    <div class="cluster-memories" style="display:flex;flex-direction:column;gap:var(--space-2);">
                        ${cluster.memories.slice(0, 5).map(m => `
                            <div style="font-size:var(--text-sm);color:var(--text-secondary);padding:var(--space-2) var(--space-3);background:var(--surface-1);border-radius:var(--radius-sm);">
                                ${escapeHtml(truncateText(m.content, 150))}
                            </div>
                        `).join('')}
                        ${cluster.count > 5 ? `<span style="font-size:var(--text-xs);color:var(--text-muted);padding-left:var(--space-3);">+ ${cluster.count - 5} more</span>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }
};
