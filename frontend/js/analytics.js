/**
 * NeuroChat — Analytics Dashboard Logic
 */

const AnalyticsDashboard = {
    init() {
        // Nothing to bind initially
    },

    async loadAnalytics() {
        try {
            const overview = await api.getAnalyticsOverview();
            this.renderOverview(overview);
            this.renderCharts(overview);
            this.loadSearchStats();
        } catch (error) {
            console.error('Failed to load analytics:', error);
            showToast('Failed to load analytics', 'error');
        }
    },

    renderOverview(data) {
        document.getElementById('analytics-conversations').textContent = data.total_conversations || 0;
        document.getElementById('analytics-messages').textContent = data.total_messages || 0;
        document.getElementById('analytics-memories').textContent = data.total_memories || 0;
        document.getElementById('analytics-documents').textContent = data.total_documents || 0;
    },

    renderCharts(data) {
        this.renderMessagesChart(data.messages_per_day || []);
        this.renderMemoryChart(data.memories_by_type || {});
    },

    renderMessagesChart(dailyData) {
        const canvas = document.getElementById('messages-canvas');
        const ctx = canvas.getContext('2d');
        const container = canvas.parentElement;

        // Set canvas size
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;

        const width = canvas.width;
        const height = canvas.height;
        const padding = { top: 20, right: 20, bottom: 40, left: 50 };
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;

        // Clear
        ctx.clearRect(0, 0, width, height);

        if (dailyData.length === 0) {
            ctx.fillStyle = '#6b6b82';
            ctx.font = '14px Inter';
            ctx.textAlign = 'center';
            ctx.fillText('No data yet', width / 2, height / 2);
            return;
        }

        const maxVal = Math.max(...dailyData.map(d => d.count), 1);

        // Draw grid lines
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
            const y = padding.top + (chartHeight / 4) * i;
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(width - padding.right, y);
            ctx.stroke();

            // Y axis labels
            ctx.fillStyle = '#6b6b82';
            ctx.font = '11px Inter';
            ctx.textAlign = 'right';
            const val = Math.round(maxVal - (maxVal / 4) * i);
            ctx.fillText(val, padding.left - 8, y + 4);
        }

        // Draw bars
        const barWidth = Math.min(30, chartWidth / dailyData.length - 4);
        const barGap = (chartWidth - barWidth * dailyData.length) / (dailyData.length + 1);

        dailyData.forEach((d, i) => {
            const x = padding.left + barGap + (barWidth + barGap) * i;
            const barHeight = (d.count / maxVal) * chartHeight;
            const y = padding.top + chartHeight - barHeight;

            // Gradient bar
            const gradient = ctx.createLinearGradient(x, y, x, padding.top + chartHeight);
            gradient.addColorStop(0, '#6366f1');
            gradient.addColorStop(1, '#a855f7');

            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.roundRect(x, y, barWidth, barHeight, [4, 4, 0, 0]);
            ctx.fill();

            // X axis labels
            ctx.fillStyle = '#6b6b82';
            ctx.font = '10px Inter';
            ctx.textAlign = 'center';
            const label = d.date ? d.date.slice(5) : '';
            ctx.fillText(label, x + barWidth / 2, height - padding.bottom + 16);
        });
    },

    renderMemoryChart(byType) {
        const canvas = document.getElementById('memory-canvas');
        const ctx = canvas.getContext('2d');
        const container = canvas.parentElement;

        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;

        const width = canvas.width;
        const height = canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(width, height) / 2 - 40;

        ctx.clearRect(0, 0, width, height);

        const entries = Object.entries(byType);
        const total = entries.reduce((sum, [, count]) => sum + count, 0);

        if (total === 0) {
            ctx.fillStyle = '#6b6b82';
            ctx.font = '14px Inter';
            ctx.textAlign = 'center';
            ctx.fillText('No memories yet', centerX, centerY);
            return;
        }

        const colors = {
            episodic: '#6366f1',
            semantic: '#a855f7',
            procedural: '#22c55e'
        };

        let startAngle = -Math.PI / 2;

        entries.forEach(([type, count]) => {
            const sliceAngle = (count / total) * Math.PI * 2;
            const endAngle = startAngle + sliceAngle;

            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.arc(centerX, centerY, radius, startAngle, endAngle);
            ctx.closePath();
            ctx.fillStyle = colors[type] || '#4a4a60';
            ctx.fill();

            // Label
            const midAngle = startAngle + sliceAngle / 2;
            const labelRadius = radius * 0.65;
            const labelX = centerX + Math.cos(midAngle) * labelRadius;
            const labelY = centerY + Math.sin(midAngle) * labelRadius;

            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 12px Inter';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            const percent = Math.round((count / total) * 100);
            if (percent > 5) {
                ctx.fillText(`${percent}%`, labelX, labelY);
            }

            startAngle = endAngle;
        });

        // Center hole (donut)
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius * 0.5, 0, Math.PI * 2);
        ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--bg-primary').trim() || '#0a0a0f';
        ctx.fill();

        // Center text
        ctx.fillStyle = '#f0f0f5';
        ctx.font = 'bold 24px Inter';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(total, centerX, centerY - 8);
        ctx.fillStyle = '#6b6b82';
        ctx.font = '11px Inter';
        ctx.fillText('Total', centerX, centerY + 12);

        // Legend
        let legendY = height - 20;
        let legendX = 10;
        entries.forEach(([type, count]) => {
            ctx.fillStyle = colors[type] || '#4a4a60';
            ctx.fillRect(legendX, legendY - 6, 10, 10);
            ctx.fillStyle = '#a0a0b8';
            ctx.font = '11px Inter';
            ctx.textAlign = 'left';
            ctx.fillText(`${type} (${count})`, legendX + 14, legendY + 2);
            legendX += ctx.measureText(`${type} (${count})`).width + 30;
        });
    },

    async loadSearchStats() {
        try {
            const stats = await api.getSearchStats();
            const container = document.getElementById('search-stats');

            const entries = Object.entries(stats);
            if (entries.length === 0) {
                container.innerHTML = '<p class="empty-state">No search indices created yet</p>';
                return;
            }

            container.innerHTML = entries.map(([name, data]) => `
                <div class="search-stat-item">
                    <div class="search-stat-name">${escapeHtml(name)}</div>
                    <div class="search-stat-value">${data.total_vectors || 0}</div>
                    <div class="search-stat-label">vectors (${data.dimension}D)</div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Failed to load search stats:', error);
        }
    }
};
