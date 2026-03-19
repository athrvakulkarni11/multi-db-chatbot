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

    canvas: null,
    ctx: null,
    dragNode: null,
    hoverNode: null,
    mouseX: 0,
    mouseY: 0,
    isSimulating: false,

    renderGraph(data) {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }

        this.canvas = document.getElementById('kg-canvas');
        this.ctx = this.canvas.getContext('2d');
        const container = document.getElementById('kg-container');
        const emptyMsg = document.getElementById('kg-empty');

        if (!data.nodes || data.nodes.length === 0) {
            if (emptyMsg) emptyMsg.style.display = 'flex';
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            return;
        }
        if (emptyMsg) emptyMsg.style.display = 'none';

        // Resize handler with High-DPI support
        const resize = () => {
            const dpr = window.devicePixelRatio || 1;
            const rect = container.getBoundingClientRect();
            this.canvas.width = rect.width * dpr;
            this.canvas.height = rect.height * dpr;
            this.canvas.style.width = `${rect.width}px`;
            this.canvas.style.height = `${rect.height}px`;
            this.ctx = this.canvas.getContext('2d');
            // We do not use ctx.scale here because we handle physical coords directly
        };
        resize();
        window.addEventListener('resize', resize);

        const width = this.canvas.width;
        const height = this.canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;

        const dpr = window.devicePixelRatio || 1;
        // Initialize nodes
        this.nodes = data.nodes.map((node, i) => {
            const angle = Math.random() * Math.PI * 2;
            const radius = Math.random() * Math.min(width, height) * 0.4;
            return {
                ...node,
                x: centerX + Math.cos(angle) * Math.max(50 * dpr, radius),
                y: centerY + Math.sin(angle) * Math.max(50 * dpr, radius),
                vx: 0,
                vy: 0,
                radius: Math.max(20, Math.min(45, 18 + (node.count || 1) * 6)) * dpr
            };
        });

        this.edges = data.edges || [];

        // Bind Mouse Events
        this._bindCanvasEvents();

        this.isSimulating = true;
        this._animate();
    },

    _bindCanvasEvents() {
        // Remove old listeners to avoid duplicates
        const newCanvas = this.canvas.cloneNode(true);
        // Ensure properties copy over
        newCanvas.width = this.canvas.width;
        newCanvas.height = this.canvas.height;
        
        this.canvas.parentNode.replaceChild(newCanvas, this.canvas);
        this.canvas = newCanvas;
        this.ctx = this.canvas.getContext('2d');

        const getMousePos = (e) => {
            const rect = this.canvas.getBoundingClientRect();
            return {
                x: (e.clientX - rect.left) * (this.canvas.width / rect.width),
                y: (e.clientY - rect.top) * (this.canvas.height / rect.height)
            };
        };

        this.canvas.addEventListener('mousedown', (e) => {
            const pos = getMousePos(e);
            // Find clicked node (reverse order for top-most)
            for (let i = this.nodes.length - 1; i >= 0; i--) {
                const node = this.nodes[i];
                const dx = pos.x - node.x;
                const dy = pos.y - node.y;
                if (dx * dx + dy * dy <= node.radius * node.radius) {
                    this.dragNode = node;
                    node.vx = 0;
                    node.vy = 0;
                    break;
                }
            }
        });

        this.canvas.addEventListener('mousemove', (e) => {
            const pos = getMousePos(e);
            this.mouseX = pos.x;
            this.mouseY = pos.y;

            if (this.dragNode) {
                this.dragNode.x = pos.x;
                this.dragNode.y = pos.y;
                this.dragNode.vx = 0;
                this.dragNode.vy = 0;
                this.isSimulating = true; // Wake up physics
            } else {
                // Check hover
                this.hoverNode = null;
                for (let i = this.nodes.length - 1; i >= 0; i--) {
                    const node = this.nodes[i];
                    const dx = pos.x - node.x;
                    const dy = pos.y - node.y;
                    if (dx * dx + dy * dy <= node.radius * node.radius) {
                        this.hoverNode = node;
                        this.canvas.style.cursor = 'pointer';
                        break;
                    }
                }
                if (!this.hoverNode) this.canvas.style.cursor = 'default';
            }
        });

        this.canvas.addEventListener('mouseup', () => {
            this.dragNode = null;
        });

        this.canvas.addEventListener('mouseleave', () => {
            this.dragNode = null;
            this.hoverNode = null;
        });
    },

    _animate() {
        if (!this.ctx) return;
        this.animationFrame = requestAnimationFrame(() => this._animate());

        const width = this.canvas.width;
        const height = this.canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;

        let totalVelocity = 0;

        const dpr = window.devicePixelRatio || 1;
        
        // Physics Step
        if (this.isSimulating) {
            const nodeMap = {};
            this.nodes.forEach(n => nodeMap[n.id] = n);

            // Repulsion
            for (let i = 0; i < this.nodes.length; i++) {
                for (let j = i + 1; j < this.nodes.length; j++) {
                    const n1 = this.nodes[i];
                    const n2 = this.nodes[j];
                    const dx = n2.x - n1.x;
                    const dy = n2.y - n1.y;
                    const distSq = Math.max(1, dx * dx + dy * dy);
                    const dist = Math.sqrt(distSq);
                    
                    // Stronger repulsion for close nodes
                    const force = (3000 * dpr * dpr) / distSq;
                    const fx = (dx / dist) * force;
                    const fy = (dy / dist) * force;

                    if (n1 !== this.dragNode) { n1.vx -= fx; n1.vy -= fy; }
                    if (n2 !== this.dragNode) { n2.vx += fx; n2.vy += fy; }
                }
            }

            // Attraction (Edges)
            for (const edge of this.edges) {
                const source = nodeMap[edge.source];
                const target = nodeMap[edge.target];
                if (!source || !target) continue;

                const dx = target.x - source.x;
                const dy = target.y - source.y;
                const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
                
                // Ideal spring length ~150px
                const force = (dist - 150 * dpr) * 0.02;
                const fx = (dx / dist) * force;
                const fy = (dy / dist) * force;

                if (source !== this.dragNode) { source.vx += fx; source.vy += fy; }
                if (target !== this.dragNode) { target.vx -= fx; target.vy -= fy; }
            }

            // Center Gravity & Update
            for (const node of this.nodes) {
                if (node !== this.dragNode) {
                    node.vx += (centerX - node.x) * 0.005;
                    node.vy += (centerY - node.y) * 0.005;
                    node.x += node.vx;
                    node.y += node.vy;
                    node.vx *= 0.85; // Friction
                    node.vy *= 0.85;
                }
                
                // Bounds
                node.x = Math.max(node.radius + 5, Math.min(width - node.radius - 5, node.x));
                node.y = Math.max(node.radius + 5, Math.min(height - node.radius - 5, node.y));
                
                totalVelocity += Math.abs(node.vx) + Math.abs(node.vy);
            }

            // Sleep if stabilized
            if (totalVelocity < 0.5 && !this.dragNode) {
                this.isSimulating = false;
            }
        }

        this._draw();
    },

    _draw() {
        const width = this.canvas.width;
        const height = this.canvas.height;
        const dpr = window.devicePixelRatio || 1;
        const ctx = this.ctx;

        ctx.clearRect(0, 0, width, height);

        const typeColors = {
            'PERSON': '#6366f1', 'PLACE': '#22c55e', 'ORG': '#f59e0b',
            'CONCEPT': '#a855f7', 'TECH': '#3b82f6', 'EVENT': '#ef4444',
            'OTHER': '#64748b'
        };

        const nodeMap = {};
        this.nodes.forEach(n => nodeMap[n.id] = n);

        // Draw Edges
        ctx.lineWidth = 1.5;
        for (const edge of this.edges) {
            const source = nodeMap[edge.source];
            const target = nodeMap[edge.target];
            if (!source || !target) continue;

            const isHovered = this.hoverNode === source || this.hoverNode === target;
            
            ctx.beginPath();
            ctx.moveTo(source.x, source.y);
            ctx.lineTo(target.x, target.y);
            ctx.strokeStyle = isHovered ? 'rgba(255, 255, 255, 0.4)' : 'rgba(160, 160, 184, 0.15)';
            ctx.stroke();

            // Arrow head
            const angle = Math.atan2(target.y - source.y, target.x - source.x);
            const arrowX = target.x - Math.cos(angle) * (target.radius + 5);
            const arrowY = target.y - Math.sin(angle) * (target.radius + 5);
            ctx.beginPath();
            ctx.moveTo(arrowX, arrowY);
            ctx.lineTo(arrowX - 8 * Math.cos(angle - Math.PI/6), arrowY - 8 * Math.sin(angle - Math.PI/6));
            ctx.lineTo(arrowX - 8 * Math.cos(angle + Math.PI/6), arrowY - 8 * Math.sin(angle + Math.PI/6));
            ctx.fillStyle = ctx.strokeStyle;
            ctx.fill();

            // Edge label
            if (edge.relation && (isHovered || this.dragNode)) {
                const midX = (source.x + target.x) / 2;
                const midY = (source.y + target.y) / 2;
                ctx.fillStyle = isHovered ? '#ffffff' : 'rgba(160, 160, 184, 0.8)';
                ctx.font = isHovered ? `bold ${10 * dpr}px Inter` : `${9 * dpr}px Inter`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                // Background wrapper for text
                const textWidth = ctx.measureText(edge.relation).width;
                ctx.fillStyle = 'rgba(15, 23, 42, 0.8)';
                ctx.fillRect(midX - textWidth/2 - 4*dpr, midY - 6*dpr, textWidth + 8*dpr, 12*dpr);
                
                ctx.fillStyle = isHovered ? '#60a5fa' : 'rgba(160, 160, 184, 0.9)';
                ctx.fillText(edge.relation, midX, midY);
            }
        }

        // Draw Nodes
        for (const node of this.nodes) {
            const color = typeColors[node.type] || typeColors.OTHER;
            const isHovered = this.hoverNode === node;
            const isDragged = this.dragNode === node;

            // Glow
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius + (isHovered ? 8 : 2), 0, Math.PI * 2);
            ctx.fillStyle = isHovered ? color + '40' : color + '15';
            ctx.fill();

            // Body
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
            const gradient = ctx.createRadialGradient(
                node.x - node.radius * 0.3, node.y - node.radius * 0.3, 0,
                node.x, node.y, node.radius
            );
            gradient.addColorStop(0, isHovered ? '#ffffff' : color);
            gradient.addColorStop(1, color + 'e0');
            ctx.fillStyle = gradient;
            ctx.fill();

            // Border
            ctx.strokeStyle = isHovered ? '#ffffff' : color;
            ctx.lineWidth = isHovered ? 3 : 1;
            ctx.stroke();

            // Label
            ctx.fillStyle = '#ffffff';
            ctx.font = `bold ${Math.max(10, 14 - Math.floor(node.label.length / 5)) * dpr}px Inter`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            const displayLabel = node.label.length > 15 && !isHovered ? node.label.substring(0, 13) + '…' : node.label;
            ctx.fillText(displayLabel, node.x, node.y);

            // Type
            if (node.radius >= 25 || isHovered) {
                ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
                ctx.font = `${8 * dpr}px Inter`;
                ctx.fillText(node.type, node.x, node.y + 12 * dpr);
            }
        }

        // Legend
        let legendX = 20;
        const legendY = height - 20;
        ctx.font = '11px Inter';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        for (const [type, color] of Object.entries(typeColors)) {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(legendX + 4, legendY, 5, 0, Math.PI*2);
            ctx.fill();
            ctx.fillStyle = '#cbd5e1';
            ctx.fillText(type, legendX + 14, legendY);
            legendX += ctx.measureText(type).width + 30;
            if (legendX > width - 80) break;
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
