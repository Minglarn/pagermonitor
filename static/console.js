/**
 * PagerMonitor - Real-time Docker & System Console
 * Stödjer realtidsströmning via SSE, nivåfärgning, ANSI-färger,
 * radbrytning (wrap), autoscroll, filtrering, sökning och justerbar höjd.
 * Strikt utan emojis.
 */

(function () {
    'use strict';

    // State
    const state = {
        isOpen: localStorage.getItem('pagermonitor-console-open') === 'true',
        height: parseInt(localStorage.getItem('pagermonitor-console-height') || '280', 10),
        isMaximized: false,
        wrapLines: localStorage.getItem('pagermonitor-console-wrap') !== 'false', // Standard: radbrytning PÅ
        autoScroll: localStorage.getItem('pagermonitor-console-autoscroll') !== 'false', // Standard: autoscroll PÅ
        activeFilter: localStorage.getItem('pagermonitor-console-filter') || 'ALL',
        searchQuery: '',
        logs: [],
        maxLogsInMemory: 1500,
        eventSource: null
    };

    // Sanitize HTML to prevent XSS
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // Convert ANSI escape codes to styled HTML spans
    function parseAnsi(text) {
        if (!text) return '';
        let escaped = escapeHtml(text);
        
        // ANSI SGR codes
        escaped = escaped.replace(/\x1b\[0m/g, '</span>');
        escaped = escaped.replace(/\x1b\[1m/g, '<span class="ansi-bold">');
        escaped = escaped.replace(/\x1b\[31m/g, '<span class="ansi-red">');
        escaped = escaped.replace(/\x1b\[32m/g, '<span class="ansi-green">');
        escaped = escaped.replace(/\x1b\[33m/g, '<span class="ansi-yellow">');
        escaped = escaped.replace(/\x1b\[34m/g, '<span class="ansi-blue">');
        escaped = escaped.replace(/\x1b\[35m/g, '<span class="ansi-magenta">');
        escaped = escaped.replace(/\x1b\[36m/g, '<span class="ansi-cyan">');
        escaped = escaped.replace(/\x1b\[90m/g, '<span class="ansi-gray">');
        // Clean remaining unhandled escape codes
        escaped = escaped.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '');

        return escaped;
    }

    // Determine CSS class for level
    function getLevelClass(level) {
        const lvl = (level || '').toLowerCase();
        if (lvl === 'info') return 'lvl-info';
        if (lvl === 'warning' || lvl === 'warn') return 'lvl-warning';
        if (lvl === 'error' || lvl === 'critical') return 'lvl-error';
        if (lvl === 'debug') return 'lvl-debug';
        return 'lvl-raw';
    }

    // Create DOM structure
    function buildConsoleDOM() {
        if (document.getElementById('pagerConsoleDock')) return;

        const dock = document.createElement('div');
        dock.id = 'pagerConsoleDock';
        dock.className = 'console-dock' + (state.isOpen ? '' : ' collapsed');
        dock.style.height = state.isOpen ? `${state.height}px` : '38px';
        document.documentElement.style.setProperty('--console-current-height', `${state.height}px`);

        dock.innerHTML = `
            <div class="console-resize-handle" id="consoleResizeHandle" title="Dra för att ändra panelens höjd"></div>
            
            <div class="console-header" id="consoleHeaderBar">
                <div class="console-header-left">
                    <span class="console-title">
                        <i class="fas fa-terminal"></i> Konsol
                    </span>
                    <span class="console-live-badge" title="Direktansluten till Docker och systemlogg">
                        <span class="console-live-dot"></span> Live
                    </span>
                    <span class="console-count-badge" id="consoleCountBadge">0 rader</span>
                    <div class="console-ticker" id="consoleTicker">Väntar på loggar...</div>
                </div>

                <div class="console-header-tools" onclick="event.stopPropagation()">
                    <div class="console-filter-group" style="display: flex; gap: 4px;">
                        <button class="console-filter-btn ${state.activeFilter === 'ALL' ? 'active' : ''}" data-filter="ALL">Alla</button>
                        <button class="console-filter-btn ${state.activeFilter === 'DECODED' ? 'active' : ''}" data-filter="DECODED">DECODED</button>
                        <button class="console-filter-btn ${state.activeFilter === 'INFO' ? 'active' : ''}" data-filter="INFO">Info</button>
                        <button class="console-filter-btn ${state.activeFilter === 'WARNING' ? 'active' : ''}" data-filter="WARNING">Varningar</button>
                        <button class="console-filter-btn ${state.activeFilter === 'ERROR' ? 'active' : ''}" data-filter="ERROR">Fel</button>
                        <button class="console-filter-btn ${state.activeFilter === 'SDR' ? 'active' : ''}" data-filter="SDR">SDR / System</button>
                    </div>

                    <div class="console-search-box">
                        <i class="fas fa-search"></i>
                        <input type="text" id="consoleSearchInput" placeholder="Sök i logg..." value="${escapeHtml(state.searchQuery)}">
                    </div>
                </div>

                <div class="console-header-actions" onclick="event.stopPropagation()">
                    <button class="console-action-btn ${state.wrapLines ? 'active' : ''}" id="consoleWrapBtn" title="Växla radbrytning (Word-wrap)">
                        <i class="fas fa-align-left"></i> Radbryt
                    </button>
                    <button class="console-action-btn ${state.autoScroll ? 'active' : ''}" id="consoleAutoScrollBtn" title="Växla automatisk rullning till botten">
                        <i class="fas fa-arrow-down"></i> Autoscroll
                    </button>
                    <button class="console-action-btn" id="consoleClearBtn" title="Rensa loggvyn">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                    <button class="console-action-btn" id="consoleDownloadBtn" title="Ladda ner logg som textfil">
                        <i class="fas fa-download"></i>
                    </button>
                    <button class="console-action-btn" id="consoleMaximizeBtn" title="Maximera / Återställ storlek">
                        <i class="fas fa-expand"></i>
                    </button>
                    <button class="console-action-btn toggle-chevron" id="consoleToggleBtn" title="Minimera / Expandera konsol">
                        <i class="fas fa-chevron-${state.isOpen ? 'down' : 'up'}"></i>
                    </button>
                </div>
            </div>

            <div class="console-body" id="consoleBody">
                <div class="console-logs-list ${state.wrapLines ? 'wrap-lines' : ''}" id="consoleLogsList">
                    <div class="console-empty-state" id="consoleEmptyState">
                        <i class="fas fa-circle-notch fa-spin"></i> Hämtar systemlogg...
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(dock);
        updateBodyClass();
        attachEventListeners();
    }

    function updateBodyClass() {
        if (state.isOpen) {
            document.body.classList.add('console-open');
        } else {
            document.body.classList.remove('console-open');
        }
    }

    // Attach interaction handlers
    function attachEventListeners() {
        const dock = document.getElementById('pagerConsoleDock');
        const header = document.getElementById('consoleHeaderBar');
        const toggleBtn = document.getElementById('consoleToggleBtn');
        const maximizeBtn = document.getElementById('consoleMaximizeBtn');
        const wrapBtn = document.getElementById('consoleWrapBtn');
        const autoScrollBtn = document.getElementById('consoleAutoScrollBtn');
        const clearBtn = document.getElementById('consoleClearBtn');
        const downloadBtn = document.getElementById('consoleDownloadBtn');
        const searchInput = document.getElementById('consoleSearchInput');
        const filterBtns = dock.querySelectorAll('.console-filter-btn');
        const consoleBody = document.getElementById('consoleBody');
        const resizeHandle = document.getElementById('consoleResizeHandle');

        // Toggle open/collapse when clicking header (except tools/actions)
        header.addEventListener('click', (e) => {
            if (e.target.closest('.console-header-tools') || e.target.closest('.console-header-actions')) return;
            toggleOpen();
        });

        toggleBtn.addEventListener('click', toggleOpen);

        // Maximize
        maximizeBtn.addEventListener('click', () => {
            if (!state.isOpen) {
                state.isOpen = true;
                saveState();
            }
            state.isMaximized = !state.isMaximized;
            if (state.isMaximized) {
                dock.style.height = '75vh';
                maximizeBtn.innerHTML = '<i class="fas fa-compress"></i>';
                maximizeBtn.classList.add('active');
            } else {
                dock.style.height = `${state.height}px`;
                maximizeBtn.innerHTML = '<i class="fas fa-expand"></i>';
                maximizeBtn.classList.remove('active');
            }
            dock.classList.remove('collapsed');
            updateToggleIcon();
            updateBodyClass();
            scrollBottomIfEnabled(true);
        });

        // Wrap toggle
        wrapBtn.addEventListener('click', () => {
            state.wrapLines = !state.wrapLines;
            localStorage.setItem('pagermonitor-console-wrap', state.wrapLines);
            wrapBtn.classList.toggle('active', state.wrapLines);
            const list = document.getElementById('consoleLogsList');
            if (list) list.classList.toggle('wrap-lines', state.wrapLines);
        });

        // AutoScroll toggle
        autoScrollBtn.addEventListener('click', () => {
            state.autoScroll = !state.autoScroll;
            localStorage.setItem('pagermonitor-console-autoscroll', state.autoScroll);
            autoScrollBtn.classList.toggle('active', state.autoScroll);
            if (state.autoScroll) scrollBottomIfEnabled(true);
        });

        // User manual scroll detection: pause autoscroll if user scrolls up
        consoleBody.addEventListener('scroll', () => {
            if (!state.autoScroll) return;
            const threshold = 30;
            const isNearBottom = consoleBody.scrollHeight - consoleBody.scrollTop - consoleBody.clientHeight <= threshold;
            if (!isNearBottom && state.autoScroll) {
                // Keep the setting, but don't force scroll while user is inspecting
            }
        });

        // Clear local log view
        clearBtn.addEventListener('click', () => {
            state.logs = [];
            renderLogs();
        });

        // Download log
        downloadBtn.addEventListener('click', () => {
            const lines = state.logs.map(l => l.raw || `${l.timestamp} [${l.level}] ${l.name}: ${l.message}`).join('\n');
            const blob = new Blob([lines], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const dateStr = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
            a.href = url;
            a.download = `pagermonitor-console-${dateStr}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });

        // Search input
        searchInput.addEventListener('input', (e) => {
            state.searchQuery = e.target.value.toLowerCase();
            renderLogs();
        });

        // Filter buttons
        filterBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetFilter = btn.getAttribute('data-filter');
                setActiveFilter(targetFilter, true);
            });
        });

        // Sync filter across browser tabs & visibility changes
        window.addEventListener('storage', (e) => {
            if (e.key === 'pagermonitor-console-filter') {
                const newFilter = e.newValue || 'ALL';
                if (state.activeFilter !== newFilter) {
                    setActiveFilter(newFilter, true);
                }
            }
        });

        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                const savedFilter = localStorage.getItem('pagermonitor-console-filter') || 'ALL';
                if (state.activeFilter !== savedFilter) {
                    setActiveFilter(savedFilter, true);
                }
            }
        });

        // Drag to resize height
        let isDragging = false;
        let startY = 0;
        let startHeight = 0;

        resizeHandle.addEventListener('mousedown', (e) => {
            if (!state.isOpen) return;
            isDragging = true;
            startY = e.clientY;
            startHeight = dock.offsetHeight;
            resizeHandle.classList.add('active');
            document.body.style.userSelect = 'none';
            e.preventDefault();
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const deltaY = startY - e.clientY;
            let newHeight = startHeight + deltaY;
            const minHeight = 160;
            const maxHeight = window.innerHeight * 0.85;

            if (newHeight < minHeight) newHeight = minHeight;
            if (newHeight > maxHeight) newHeight = maxHeight;

            dock.style.height = `${newHeight}px`;
            state.height = newHeight;
            document.documentElement.style.setProperty('--console-current-height', `${newHeight}px`);
        });

        window.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                resizeHandle.classList.remove('active');
                document.body.style.userSelect = '';
                localStorage.setItem('pagermonitor-console-height', state.height);
            }
        });
    }

    function toggleOpen() {
        const dock = document.getElementById('pagerConsoleDock');
        state.isOpen = !state.isOpen;
        state.isMaximized = false;
        saveState();

        if (state.isOpen) {
            dock.classList.remove('collapsed');
            dock.style.height = `${state.height}px`;
            scrollBottomIfEnabled(true);
        } else {
            dock.classList.add('collapsed');
            dock.style.height = '38px';
        }

        updateToggleIcon();
        updateBodyClass();
    }

    function updateToggleIcon() {
        const toggleBtn = document.getElementById('consoleToggleBtn');
        if (toggleBtn) {
            toggleBtn.innerHTML = `<i class="fas fa-chevron-${state.isOpen ? 'down' : 'up'}"></i>`;
        }
        const maxBtn = document.getElementById('consoleMaximizeBtn');
        if (maxBtn && !state.isMaximized) {
            maxBtn.innerHTML = '<i class="fas fa-expand"></i>';
            maxBtn.classList.remove('active');
        }
    }

    function saveState() {
        localStorage.setItem('pagermonitor-console-open', state.isOpen);
    }

    function scrollBottomIfEnabled(force = false) {
        if (!state.autoScroll && !force) return;
        const consoleBody = document.getElementById('consoleBody');
        if (consoleBody) {
            consoleBody.scrollTop = consoleBody.scrollHeight;
        }
    }

    // Filter logic
    function logMatchesFilter(log) {
        const lvl = (log.level || '').toUpperCase();
        const src = (log.name || '').toLowerCase();

        // Filter criteria
        if (state.activeFilter === 'DECODED') {
            const raw = (log.raw || log.message || '');
            if (!raw.includes('DECODED ->')) return false;
        }
        if (state.activeFilter === 'INFO' && lvl !== 'INFO') return false;
        if (state.activeFilter === 'WARNING' && lvl !== 'WARNING' && lvl !== 'WARN') return false;
        if (state.activeFilter === 'ERROR' && lvl !== 'ERROR' && lvl !== 'CRITICAL') return false;
        if (state.activeFilter === 'SDR') {
            const isSdrOrSystem = src.includes('sdr') || src.includes('multimon') || src.includes('rtl') || src.includes('supervisor') || lvl === 'SYSTEM';
            if (!isSdrOrSystem) return false;
        }

        // Search text query
        if (state.searchQuery) {
            const fullText = `${log.timestamp || ''} ${log.level || ''} ${log.name || ''} ${log.message || ''} ${log.raw || ''}`.toLowerCase();
            if (!fullText.includes(state.searchQuery)) return false;
        }

        return true;
    }

    // Create a DOM node for a single log row
    function createLogRowNode(log) {
        const row = document.createElement('div');
        const lvlLower = (log.level || 'info').toLowerCase();
        const isDecoded = (log.raw || log.message || '').includes('DECODED ->');
        row.className = `console-log-row ${lvlLower === 'error' ? 'is-error' : ''} ${lvlLower === 'warning' || lvlLower === 'warn' ? 'is-warning' : ''} ${isDecoded ? 'is-decoded' : ''}`;

        const time = escapeHtml(log.time || (log.timestamp ? log.timestamp.split(' ')[1] : ''));
        const levelBadge = `<span class="console-log-level ${getLevelClass(log.level)}">${escapeHtml(log.level || 'INFO')}</span>`;
        const nameBadge = `<span class="console-log-name">[${escapeHtml(log.name || 'app')}]</span>`;
        let parsedMsg = parseAnsi(log.message || log.raw || '');
        if (isDecoded) {
            parsedMsg = parsedMsg.replace('DECODED -&gt;', '<span class="console-tag-decoded">DECODED &rarr;</span>');
        }

        row.innerHTML = `
            <span class="console-log-time">${time}</span>
            ${levelBadge}
            ${nameBadge}
            <span class="console-log-msg">${parsedMsg}</span>
        `;
        return row;
    }

    // Render all filtered logs
    function renderLogs() {
        const list = document.getElementById('consoleLogsList');
        const countBadge = document.getElementById('consoleCountBadge');
        if (!list) return;

        const filtered = state.logs.filter(logMatchesFilter);

        if (countBadge) {
            countBadge.innerText = `${state.logs.length} rader${state.logs.length !== filtered.length ? ` (${filtered.length} visade)` : ''}`;
        }

        if (filtered.length === 0) {
            list.innerHTML = `
                <div class="console-empty-state">
                    <i class="fas fa-info-circle"></i> Inga loggmeddelanden matchar aktuellt filter.
                </div>
            `;
            return;
        }

        // Use fragment for fast DOM rendering
        const fragment = document.createDocumentFragment();
        filtered.forEach(log => {
            fragment.appendChild(createLogRowNode(log));
        });

        list.innerHTML = '';
        list.appendChild(fragment);

        scrollBottomIfEnabled();
    }

    // Append a single new log row directly for high performance
    function appendLogRow(log) {
        state.logs.push(log);
        if (state.logs.length > state.maxLogsInMemory) {
            state.logs.shift();
        }

        // Update ticker text in minified bar
        const ticker = document.getElementById('consoleTicker');
        if (ticker) {
            ticker.innerText = `[${log.level}] ${log.name}: ${log.message}`;
        }

        const countBadge = document.getElementById('consoleCountBadge');
        if (countBadge) {
            countBadge.innerText = `${state.logs.length} rader`;
        }

        if (!logMatchesFilter(log)) return;

        const list = document.getElementById('consoleLogsList');
        if (!list) return;

        const emptyState = list.querySelector('.console-empty-state');
        if (emptyState) {
            list.innerHTML = '';
        }

        const node = createLogRowNode(log);
        list.appendChild(node);

        // Keep DOM elements bounded to avoid memory bloating
        if (list.children.length > 1000) {
            list.removeChild(list.firstElementChild);
        }

        scrollBottomIfEnabled();
    }

    // Set and persist active filter with smart history retrieval
    async function setActiveFilter(filterName, fetchIfEmpty = true) {
        state.activeFilter = filterName || 'ALL';
        localStorage.setItem('pagermonitor-console-filter', state.activeFilter);

        const filterBtns = document.querySelectorAll('.console-filter-btn');
        filterBtns.forEach(btn => {
            btn.classList.toggle('active', btn.getAttribute('data-filter') === state.activeFilter);
        });

        if (fetchIfEmpty && state.activeFilter !== 'ALL') {
            const currentMatches = state.logs.filter(logMatchesFilter);
            if (currentMatches.length < 15) {
                await fetchFilteredHistory(state.activeFilter);
            }
        }
        renderLogs();
    }

    // Fetch history for specific filter from server ring buffer
    async function fetchFilteredHistory(level) {
        try {
            const filterParam = (level && level !== 'ALL') ? `&level=${encodeURIComponent(level)}` : '';
            const res = await fetch(`/api/logs/history?limit=400${filterParam}`);
            if (!res.ok) return;
            const data = await res.json();
            if (data && data.logs && data.logs.length > 0) {
                const existingKeys = new Set(state.logs.map(l => `${l.timestamp}_${l.raw || l.message}`));
                data.logs.forEach(l => {
                    const k = `${l.timestamp}_${l.raw || l.message}`;
                    if (!existingKeys.has(k)) {
                        state.logs.push(l);
                        existingKeys.add(k);
                    }
                });
                state.logs.sort((a, b) => (a.timestamp || '').localeCompare(b.timestamp || ''));
                if (state.logs.length > state.maxLogsInMemory) {
                    state.logs = state.logs.slice(-state.maxLogsInMemory);
                }
                renderLogs();
            }
        } catch (e) {
            console.debug('Kunde inte läsa filtrerad historik:', e);
        }
    }

    // Fetch initial history honoring saved activeFilter
    async function fetchInitialHistory() {
        try {
            const filterParam = (state.activeFilter && state.activeFilter !== 'ALL') ? `&level=${encodeURIComponent(state.activeFilter)}` : '';
            const res = await fetch(`/api/logs/history?limit=400${filterParam}`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            const data = await res.json();
            if (data && data.logs) {
                state.logs = data.logs;
                renderLogs();
                // Set initial ticker
                if (state.logs.length > 0) {
                    const last = state.logs[state.logs.length - 1];
                    const ticker = document.getElementById('consoleTicker');
                    if (ticker) ticker.innerText = `[${last.level}] ${last.name}: ${last.message}`;
                }
            }
        } catch (err) {
            console.warn('PagerMonitor Console: Kunde inte hämta logghistorik:', err);
            const list = document.getElementById('consoleLogsList');
            if (list) {
                list.innerHTML = `
                    <div class="console-empty-state">
                        <i class="fas fa-exclamation-triangle" style="color: #f59e0b;"></i> Väntar på att ansluta till loggservern...
                    </div>
                `;
            }
        }
    }

    // Connect to real-time SSE stream
    function connectLogStream() {
        if (state.eventSource) {
            try { state.eventSource.close(); } catch (e) {}
        }

        state.eventSource = new EventSource('/api/logs/stream');

        state.eventSource.onopen = function () {
            const badge = document.querySelector('.console-live-badge');
            if (badge) {
                badge.innerHTML = '<span class="console-live-dot"></span> Live';
                badge.style.color = '#10b981';
            }
        };

        state.eventSource.onmessage = function (event) {
            if (!event.data) return;
            try {
                const log = JSON.parse(event.data);
                if (log && log.level) {
                    appendLogRow(log);
                }
            } catch (err) {
                // Heartbeat / ping comments
            }
        };

        state.eventSource.onerror = function () {
            const badge = document.querySelector('.console-live-badge');
            if (badge) {
                badge.innerHTML = '<span class="console-live-dot" style="background: #f59e0b; box-shadow: none;"></span> Återansluter...';
                badge.style.color = '#f59e0b';
            }
            // EventSource will automatically retry connecting
        };
    }

    // Initialize once DOM is ready
    function init() {
        buildConsoleDOM();
        fetchInitialHistory().then(() => {
            connectLogStream();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
