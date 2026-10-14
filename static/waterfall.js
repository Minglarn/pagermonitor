/**
 * Waterfall & Activity Ribbon Manager (PagerMonitor v2.0)
 * Strictly NO emojis.
 * Visualizes live 60-minute RF channel activity across SDR receivers with high-FPS canvas.
 */

window.WaterfallManager = (function () {
    let channels = {}; // Key: channelKey -> { id, name, frequency, bins: [60], lastMinuteIndex, lastSeen }
    let sdrInstances = [];
    let isCollapsed = false;
    let onFilterCallback = null;
    let activeFilterChannel = null;
    let rollTimer = null;
    let tooltipEl = null;

    const BIN_COUNT = 60; // 60 minutes rolling history

    function initTooltip() {
        if (!tooltipEl) {
            tooltipEl = document.createElement('div');
            tooltipEl.className = 'waterfall-tooltip';
            tooltipEl.id = 'waterfallTooltip';
            document.body.appendChild(tooltipEl);
        }
    }

    function getMinuteBinIndex(timestampDate, now) {
        const diffMs = now.getTime() - timestampDate.getTime();
        const diffMinutes = Math.floor(diffMs / 60000);
        if (diffMinutes < 0 || diffMinutes >= BIN_COUNT) return -1;
        return (BIN_COUNT - 1) - diffMinutes; // 59 is current minute, 0 is 59 mins ago
    }

    function createChannelObj(id, name, frequency) {
        const bins = [];
        for (let i = 0; i < BIN_COUNT; i++) {
            bins.push({ total: 0, alerts: 0, duplicates: 0, pulse: 0 });
        }
        return {
            id: id,
            name: name || frequency || 'Receiver',
            frequency: frequency || 'Unknown',
            bins: bins,
            total60m: 0,
            lastSeen: null
        };
    }

    function normalizeFrequency(freq) {
        if (!freq) return 'Unknown';
        let f = String(freq).trim();
        f = f.replace(/MHz|M|Hz/gi, '').trim();
        const num = parseFloat(f);
        if (!isNaN(num)) {
            return num.toFixed(4);
        }
        return f;
    }

    function getChannelKey(frequency) {
        const normFreq = normalizeFrequency(frequency);
        return `freq_${normFreq.replace(/[^a-z0-9]/g, '_')}`;
    }

    function registerChannel(sdrName, frequency) {
        if (!frequency || frequency === 'Unknown' || frequency === 'RESTART') return null;
        const key = getChannelKey(frequency);
        const normFreq = normalizeFrequency(frequency);

        let matchedName = sdrName;
        const matchInst = sdrInstances.find(i => normalizeFrequency(i.frequency) === normFreq);
        if (matchInst && matchInst.name) {
            matchedName = matchInst.name;
        }
        if (!matchedName || matchedName === 'Unknown' || matchedName.startsWith('Freq ')) {
            if (matchInst && matchInst.name) {
                matchedName = matchInst.name;
            } else if (frequency.startsWith('4') || frequency.startsWith('39')) {
                matchedName = `TETRA ${frequency}`;
            } else {
                matchedName = `Freq ${frequency}`;
            }
        }

        if (!channels[key]) {
            channels[key] = createChannelObj(key, matchedName, frequency);
            renderChannelRows();
        } else {
            // Update to configured SDR name if previously generic
            if (matchedName && !matchedName.startsWith('Freq ') && channels[key].name !== matchedName) {
                channels[key].name = matchedName;
                if (frequency && frequency !== 'Unknown') channels[key].frequency = frequency;
                renderChannelRows();
            }
        }
        return channels[key];
    }

    function renderChannelRows() {
        const container = document.getElementById('waterfallChannels');
        const summaryContainer = document.getElementById('ribbonChannelSummary');
        if (!container) return;

        container.innerHTML = '';
        if (summaryContainer) summaryContainer.innerHTML = '';

        Object.values(channels).forEach(ch => {
            // Render row in waterfall
            const row = document.createElement('div');
            row.className = 'channel-waterfall-row';
            row.id = `waterfall-row-${ch.id}`;
            if (activeFilterChannel === ch.id) row.classList.add('active-filter');

            row.innerHTML = `
                <div class="channel-info-cell">
                    <div class="channel-indicator-dot" id="dot-${ch.id}"></div>
                    <div class="channel-text">
                        <span class="channel-name" title="${ch.name}">${ch.name}</span>
                        <span class="channel-freq" id="freq-${ch.id}">${ch.frequency}</span>
                    </div>
                </div>
                <div class="channel-canvas-cell">
                    <canvas class="waterfall-canvas" id="canvas-${ch.id}" height="24"></canvas>
                </div>
                <div class="channel-stats-cell">
                    <span id="count-${ch.id}"><strong>${ch.total60m}</strong> msgs</span>
                </div>
            `;

            // Click row to filter
            row.addEventListener('click', (e) => {
                toggleChannelFilter(ch);
            });

            container.appendChild(row);

            // Setup canvas interactions & resizing
            const canvas = row.querySelector('.waterfall-canvas');
            setupCanvasInteraction(canvas, ch);

            // Render summary pill in ribbon header
            if (summaryContainer) {
                const pill = document.createElement('div');
                pill.className = 'ribbon-summary-pill';
                pill.id = `summary-pill-${ch.id}`;
                if (activeFilterChannel === ch.id) pill.classList.add('active-filter');
                pill.innerHTML = `
                    <span class="ribbon-summary-dot" id="summary-dot-${ch.id}"></span>
                    <span>${ch.name}: <strong><span id="summary-count-${ch.id}">${ch.total60m}</span></strong></span>
                `;
                pill.addEventListener('click', (e) => {
                    e.stopPropagation();
                    toggleChannelFilter(ch);
                });
                summaryContainer.appendChild(pill);
            }
        });

        drawAllCanvases();
    }

    function toggleChannelFilter(ch) {
        if (activeFilterChannel === ch.id) {
            activeFilterChannel = null;
            if (onFilterCallback) onFilterCallback('');
        } else {
            activeFilterChannel = ch.id;
            let filterTerm = ch.frequency;
            // Om kanalen är RDS, filtrera alltid på 'RDS' (matchar 'RDS-TMC' i flödet istället för 'auto')
            if (ch.name && (ch.name.toUpperCase() === 'RDS' || ch.name.toUpperCase().includes('RDS') || ch.name.toUpperCase().includes('TMC'))) {
                filterTerm = 'RDS';
            } else if (!filterTerm || filterTerm.toLowerCase() === 'auto' || filterTerm.toLowerCase() === 'scan' || filterTerm.toLowerCase() === 'unknown') {
                filterTerm = ch.name;
            }
            if (onFilterCallback) onFilterCallback(filterTerm || ch.name);
        }

        // Update UI highlights
        document.querySelectorAll('.channel-waterfall-row').forEach(r => r.classList.remove('active-filter'));
        document.querySelectorAll('.ribbon-summary-pill').forEach(p => p.classList.remove('active-filter'));

        if (activeFilterChannel) {
            const activeRow = document.getElementById(`waterfall-row-${activeFilterChannel}`);
            if (activeRow) activeRow.classList.add('active-filter');
            const activePill = document.getElementById(`summary-pill-${activeFilterChannel}`);
            if (activePill) activePill.classList.add('active-filter');
        }
    }

    function setupCanvasInteraction(canvas, channel) {
        if (!canvas) return;

        canvas.addEventListener('mousemove', (e) => {
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const colWidth = rect.width / BIN_COUNT;
            const binIdx = Math.min(BIN_COUNT - 1, Math.max(0, Math.floor(x / colWidth)));
            const bin = channel.bins[binIdx];

            // Calculate timestamp for bin
            const now = new Date();
            const minutesAgo = (BIN_COUNT - 1) - binIdx;
            const binTime = new Date(now.getTime() - minutesAgo * 60000);
            const timeStr = binTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            if (tooltipEl) {
                let alertHtml = '';
                if (bin.alerts > 0) {
                    alertHtml = `<div class="tooltip-alert">${bin.alerts} alert match${bin.alerts > 1 ? 'es' : ''}</div>`;
                }
                let dupHtml = bin.duplicates > 0 ? ` (${bin.duplicates} duplicate${bin.duplicates > 1 ? 's' : ''})` : '';

                tooltipEl.innerHTML = `
                    <div class="tooltip-header">${channel.name} (${channel.frequency}) &bull; ${timeStr}</div>
                    <div class="tooltip-body">${bin.total} message${bin.total === 1 ? '' : 's'}${dupHtml}</div>
                    ${alertHtml}
                `;
                tooltipEl.style.left = `${e.clientX}px`;
                tooltipEl.style.top = `${rect.top - 8}px`;
                tooltipEl.classList.add('show');
            }
        });

        canvas.addEventListener('mouseleave', () => {
            if (tooltipEl) tooltipEl.classList.remove('show');
        });
    }

    function drawCanvas(canvas, channel) {
        if (!canvas) return;
        const rect = canvas.getBoundingClientRect();
        if (rect.width === 0) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = 24 * dpr;

        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);

        const width = rect.width;
        const height = 24;

        ctx.clearRect(0, 0, width, height);

        const colWidth = width / BIN_COUNT;
        const gap = 1.5;
        const barWidth = Math.max(1, colWidth - gap);

        // Find max in this channel for proportional height
        let maxVal = 1;
        for (let i = 0; i < BIN_COUNT; i++) {
            if (channel.bins[i].total > maxVal) maxVal = channel.bins[i].total;
        }

        for (let i = 0; i < BIN_COUNT; i++) {
            const bin = channel.bins[i];
            const x = i * colWidth;

            // Background slot (empty bar)
            ctx.fillStyle = 'rgba(255, 255, 255, 0.04)';
            ctx.fillRect(x, 2, barWidth, height - 4);

            if (bin.total > 0) {
                // Height calculation: at least 4px, up to height - 4
                const ratio = Math.min(1, bin.total / Math.max(3, maxVal));
                const barHeight = Math.max(4, ratio * (height - 6));
                const y = height - 2 - barHeight;

                if (bin.alerts > 0) {
                    // Alert neon red/coral
                    ctx.fillStyle = '#ef4444';
                    ctx.fillRect(x, y, barWidth, barHeight);

                    // Glowing top cap
                    ctx.fillStyle = '#fca5a5';
                    ctx.fillRect(x, y, barWidth, 2);
                } else if (bin.duplicates > 0 && bin.duplicates === bin.total) {
                    // Amber for duplicates
                    ctx.fillStyle = '#f59e0b';
                    ctx.fillRect(x, y, barWidth, barHeight);
                } else {
                    // Normal cyan/blue gradient
                    const grad = ctx.createLinearGradient(0, y, 0, y + barHeight);
                    grad.addColorStop(0, '#38bdf8');
                    grad.addColorStop(1, '#0284c7');
                    ctx.fillStyle = grad;
                    ctx.fillRect(x, y, barWidth, barHeight);

                    // Subtle top highlight
                    ctx.fillStyle = '#e0f2fe';
                    ctx.fillRect(x, y, barWidth, 1.5);
                }
            }

            // Pulse on the current minute (bin 59) if recent activity
            if (i === BIN_COUNT - 1 && bin.pulse > 0) {
                ctx.strokeStyle = '#10b981';
                ctx.lineWidth = 1.5;
                ctx.strokeRect(x - 1, 1, barWidth + 2, height - 2);
            }
        }
    }

    function drawAllCanvases() {
        Object.values(channels).forEach(ch => {
            const canvas = document.getElementById(`canvas-${ch.id}`);
            if (canvas) drawCanvas(canvas, ch);
        });
    }

    function recordMessage(msg, isRealtime = false) {
        if (!msg || !msg.timestamp) return;

        // Skip TETRA basestation sync announcements from creating RF Activity channels and hit counts
        if (msg.bitrate === 'TETRA-NET' || (msg.message && (msg.message.includes('Aktiv TETRA Basstation') || msg.message.includes('Aktiv Basstation')))) {
            return;
        }

        const freq = msg.frequency || 'Unknown';
        if (freq === 'RESTART' || freq === 'Unknown') return;

        const isRdsMsg = (msg.bitrate && (msg.bitrate.includes('RDS') || msg.bitrate.includes('TMC'))) || 
                         (msg.protocol && msg.protocol.includes('RDS')) ||
                         (msg.sdr_name && msg.sdr_name.toUpperCase().includes('RDS'));

        let ch = null;
        if (isRdsMsg) {
            // Leta efter befintlig RDS-kanal (t.ex. 'RDS' med frekvens 'auto')
            const rdsKey = Object.keys(channels).find(k => channels[k].name && (channels[k].name.toUpperCase() === 'RDS' || channels[k].name.toUpperCase().includes('RDS')));
            if (rdsKey) {
                ch = channels[rdsKey];
                // Uppdatera visningsfrekvens till den aktiva låsta frekvensen om den tidigare var 'auto'
                if (freq && freq !== 'Unknown' && ch.frequency.toLowerCase() === 'auto') {
                    ch.frequency = freq;
                    const freqEl = document.getElementById(`freq-${ch.id}`);
                    if (freqEl) freqEl.textContent = freq;
                }
            }
        }

        if (!ch) {
            const sdrName = msg.sdr_name || (msg.frequency ? `Freq ${msg.frequency}` : 'Receiver');
            ch = registerChannel(sdrName, freq);
        }
        if (!ch) return;

        const msgDate = new Date(msg.timestamp);
        const now = new Date();
        const binIdx = getMinuteBinIndex(msgDate, now);

        if (binIdx >= 0 && binIdx < BIN_COUNT) {
            ch.bins[binIdx].total += 1;
            if (msg.alert_word || msg.is_alert) ch.bins[binIdx].alerts += 1;
            if (msg.is_duplicate) ch.bins[binIdx].duplicates += 1;
            ch.total60m += 1;

            if (isRealtime) {
                ch.bins[binIdx].pulse = 1;
                setTimeout(() => {
                    ch.bins[binIdx].pulse = 0;
                    const canvas = document.getElementById(`canvas-${ch.id}`);
                    if (canvas) drawCanvas(canvas, ch);
                }, 2500);

                // Flash live indicators
                const dot = document.getElementById(`dot-${ch.id}`);
                const sumDot = document.getElementById(`summary-dot-${ch.id}`);
                if (dot) {
                    dot.classList.add('rx-active');
                    setTimeout(() => dot.classList.remove('rx-active'), 1200);
                }
                if (sumDot) {
                    sumDot.classList.add('rx-flash');
                    setTimeout(() => sumDot.classList.remove('rx-flash'), 1200);
                }
            }

            // Update count badges
            const countEl = document.getElementById(`count-${ch.id}`);
            if (countEl) countEl.innerHTML = `<strong>${ch.total60m}</strong> msgs`;
            const sumCountEl = document.getElementById(`summary-count-${ch.id}`);
            if (sumCountEl) sumCountEl.textContent = ch.total60m;

            const canvas = document.getElementById(`canvas-${ch.id}`);
            if (canvas) drawCanvas(canvas, ch);
        }
    }

    function rollTimeline() {
        // Shift bins left by 1 minute
        Object.values(channels).forEach(ch => {
            ch.bins.shift();
            ch.bins.push({ total: 0, alerts: 0, duplicates: 0, pulse: 0 });

            // Recalculate 60m total
            ch.total60m = ch.bins.reduce((sum, b) => sum + b.total, 0);

            const countEl = document.getElementById(`count-${ch.id}`);
            if (countEl) countEl.innerHTML = `<strong>${ch.total60m}</strong> msgs`;
            const sumCountEl = document.getElementById(`summary-count-${ch.id}`);
            if (sumCountEl) sumCountEl.textContent = ch.total60m;
        });

        drawAllCanvases();
    }

    function toggleCollapse() {
        const panel = document.getElementById('activityRibbonPanel');
        const icon = document.getElementById('ribbonToggleIcon');
        const label = document.querySelector('.ribbon-toggle-label');
        if (!panel) return;

        isCollapsed = !isCollapsed;
        panel.classList.toggle('collapsed', isCollapsed);

        if (isCollapsed) {
            if (icon) { icon.classList.remove('fa-chevron-up'); icon.classList.add('fa-chevron-down'); }
            if (label) label.textContent = 'Show';
        } else {
            if (icon) { icon.classList.remove('fa-chevron-down'); icon.classList.add('fa-chevron-up'); }
            if (label) label.textContent = 'Hide';
            setTimeout(() => drawAllCanvases(), 50);
        }

        localStorage.setItem('pagermonitor-ribbon-collapsed', isCollapsed ? 'true' : 'false');
    }

    async function init(initialMessages = [], filterCallback = null) {
        initTooltip();
        onFilterCallback = filterCallback;

        // Default to COLLAPSED (true) unless user explicitly saved 'false'
        const savedCollapsed = localStorage.getItem('pagermonitor-ribbon-collapsed');
        const shouldCollapse = (savedCollapsed === null) ? true : (savedCollapsed === 'true');
        
        isCollapsed = shouldCollapse;
        const panel = document.getElementById('activityRibbonPanel');
        const icon = document.getElementById('ribbonToggleIcon');
        const label = document.querySelector('.ribbon-toggle-label');
        if (panel) panel.classList.toggle('collapsed', isCollapsed);
        if (icon) {
            icon.className = isCollapsed ? 'fas fa-chevron-down' : 'fas fa-chevron-up';
        }
        if (label) {
            label.textContent = isCollapsed ? 'Show' : 'Hide';
        }

        // Fetch configured SDR instances
        try {
            const res = await fetch('/api/sdr');
            if (res.ok) {
                sdrInstances = await res.json();
                sdrInstances.forEach(inst => {
                    if (inst.enabled) {
                        registerChannel(inst.name, inst.frequency);
                    }
                });
            }
        } catch (e) {
            console.warn('Could not fetch SDR instances for waterfall:', e);
        }

        // Process initial historical messages
        if (initialMessages && initialMessages.length > 0) {
            initialMessages.forEach(msg => {
                recordMessage(msg, false);
            });
        }

        renderChannelRows();

        // Window resize handler
        window.addEventListener('resize', () => {
            drawAllCanvases();
        });

        // Set up roll timer every 30 seconds
        if (rollTimer) clearInterval(rollTimer);
        let lastMinute = new Date().getMinutes();
        rollTimer = setInterval(() => {
            const curMinute = new Date().getMinutes();
            if (curMinute !== lastMinute) {
                lastMinute = curMinute;
                rollTimeline();
            }
        }, 15000);
    }

    return {
        init: init,
        recordMessage: recordMessage,
        toggleCollapse: toggleCollapse,
        drawAllCanvases: drawAllCanvases
    };
})();
