/**
 * Waterfall & Activity Ribbon Manager (PagerMonitor)
 * Strictly NO emojis.
 * RF Activity Monitor: 60-minute rolling telemetry instrument with sorting, 
 * intensity heatbars, rate counters and collapsible header.
 */

window.WaterfallManager = (function () {
    let channels = {}; // Key: channelKey -> { id, name, frequency, protocol, bins: [60], total60m: 0, lastSeen: null }
    let sdrInstances = [];
    let isCollapsed = false;
    let onFilterCallback = null;
    let activeFilterChannels = new Set();
    let rollTimer = null;
    let renderDebounceTimer = null;
    let currentSort = localStorage.getItem('pagermonitor-wf-sort') || 'count';

    const BIN_COUNT = 60; // 60 minutes rolling history

    function getMinuteBinIndex(timestampDate, now) {
        const diffMs = now.getTime() - timestampDate.getTime();
        const diffMinutes = Math.floor(diffMs / 60000);
        if (diffMinutes < 0 || diffMinutes >= BIN_COUNT) return -1;
        return (BIN_COUNT - 1) - diffMinutes; // 59 is current minute, 0 is 59 mins ago
    }

    function createChannelObj(id, name, frequency, protocol) {
        const bins = [];
        for (let i = 0; i < BIN_COUNT; i++) {
            bins.push({ total: 0, alerts: 0, duplicates: 0 });
        }
        return {
            id: id,
            name: name || frequency || 'Receiver',
            frequency: frequency || 'Unknown',
            protocol: protocol || null,
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

    function detectChannelProtocol(ch) {
        if (ch && ch.protocol) {
            const p = String(ch.protocol).toUpperCase();
            if (p.includes('HFDL')) return { name: 'HFDL', cls: 'proto-hfdl', borderCls: 'border-hfdl' };
            if (p.includes('VDL')) return { name: 'VDL2', cls: 'proto-vdl2', borderCls: 'border-vdl2' };
            if (p.includes('SATC') || p.includes('INMARSAT') || p.includes('SAT-C')) return { name: 'SAT-C', cls: 'proto-satc', borderCls: 'border-satc' };
            if (p.includes('SONDE') || p.includes('RS41') || p.includes('DFM')) return { name: 'SONDE', cls: 'proto-sonde', borderCls: 'border-sonde' };
            if (p.includes('ACARS')) return { name: 'ACARS', cls: 'proto-acars', borderCls: 'border-acars' };
            if (p.includes('TETRA')) return { name: 'TETRA', cls: 'proto-tetra', borderCls: 'border-tetra' };
            if (p.includes('RDS') || p.includes('TMC')) return { name: 'RDS', cls: 'proto-rds', borderCls: 'border-rds' };
            if (p.includes('AFSK')) return { name: 'AFSK', cls: 'proto-afsk', borderCls: 'border-afsk' };
            if (p.includes('POCSAG')) return { name: 'POCSAG', cls: 'proto-pocsag', borderCls: 'border-pocsag' };
        }

        const nameUpper = (ch && ch.name ? ch.name : '').toUpperCase();
        const freqStr = String(ch && ch.frequency ? ch.frequency : '').trim();
        const freqNum = parseFloat(freqStr.replace(/[^0-9.]/g, '')) || 0;

        if (nameUpper.includes('HFDL')) return { name: 'HFDL', cls: 'proto-hfdl', borderCls: 'border-hfdl' };
        if (nameUpper.includes('VDL') || (freqNum >= 136.5 && freqNum <= 137.0)) return { name: 'VDL2', cls: 'proto-vdl2', borderCls: 'border-vdl2' };
        if (nameUpper.includes('SATC') || nameUpper.includes('INMARSAT') || (freqNum >= 1530 && freqNum <= 1560)) return { name: 'SAT-C', cls: 'proto-satc', borderCls: 'border-satc' };
        if (nameUpper.includes('SONDE') || nameUpper.includes('BALLONG') || nameUpper.includes('RS41') || (freqNum >= 400 && freqNum <= 406)) return { name: 'SONDE', cls: 'proto-sonde', borderCls: 'border-sonde' };
        if (nameUpper.includes('ACARS') || (freqNum >= 131.0 && freqNum <= 132.0)) return { name: 'ACARS', cls: 'proto-acars', borderCls: 'border-acars' };
        if (nameUpper.includes('TETRA') || nameUpper.includes('RAKEL') || (freqNum >= 380 && freqNum <= 395)) return { name: 'TETRA', cls: 'proto-tetra', borderCls: 'border-tetra' };
        if (nameUpper.includes('RDS') || nameUpper.includes('TMC') || freqStr.toLowerCase() === 'auto' || (freqNum >= 87.5 && freqNum <= 108.0)) return { name: 'RDS', cls: 'proto-rds', borderCls: 'border-rds' };
        if (nameUpper.includes('AFSK') || (freqNum >= 144 && freqNum <= 146)) return { name: 'AFSK', cls: 'proto-afsk', borderCls: 'border-afsk' };
        if (nameUpper.includes('POCSAG') || (freqNum >= 169 && freqNum <= 174)) return { name: 'POCSAG', cls: 'proto-pocsag', borderCls: 'border-pocsag' };

        return { name: 'POCSAG', cls: 'proto-pocsag', borderCls: 'border-pocsag' };
    }

    function registerChannel(sdrName, frequency, protocol = null) {
        if (!frequency || frequency === 'Unknown' || frequency === 'RESTART') return null;
        const key = getChannelKey(frequency);
        const normFreq = normalizeFrequency(frequency);

        let matchedName = sdrName;
        let matchedProto = protocol;
        const matchInst = sdrInstances.find(i => normalizeFrequency(i.frequency) === normFreq);
        if (matchInst) {
            if (matchInst.name) matchedName = matchInst.name;
            if (matchInst.protocol) matchedProto = matchInst.protocol;
        }

        if (!matchedName || matchedName === 'Unknown' || matchedName.startsWith('Freq ')) {
            if (matchInst && matchInst.name) {
                matchedName = matchInst.name;
            } else if (matchedName && (matchedName.toUpperCase().includes('SONDE') || matchedName.toUpperCase().includes('RADIO'))) {
                // Behåll radiosondnamn
            } else if ((frequency.startsWith('38') || frequency.startsWith('39')) && (!matchedName || matchedName.toUpperCase().includes('TETRA'))) {
                matchedName = `TETRA ${frequency}`;
            } else if (!matchedName || matchedName === 'Unknown') {
                matchedName = `Freq ${frequency}`;
            }
        }

        if (!channels[key]) {
            channels[key] = createChannelObj(key, matchedName, frequency, matchedProto);
            scheduleRender();
        } else {
            let changed = false;
            if (matchedName && !matchedName.startsWith('Freq ') && channels[key].name !== matchedName) {
                channels[key].name = matchedName;
                changed = true;
            }
            if (frequency && frequency !== 'Unknown' && channels[key].frequency !== frequency) {
                channels[key].frequency = frequency;
                changed = true;
            }
            if (matchedProto && !channels[key].protocol) {
                channels[key].protocol = matchedProto;
                changed = true;
            }
            if (changed) scheduleRender();
        }
        return channels[key];
    }

    function formatLastSeen(ch) {
        if (!ch.total60m || ch.total60m === 0) {
            return '<span class="badge-silent">TYST 1H</span>';
        }
        let lastActiveBinIdx = -1;
        for (let i = BIN_COUNT - 1; i >= 0; i--) {
            if (ch.bins[i].total > 0) {
                lastActiveBinIdx = i;
                break;
            }
        }
        if (lastActiveBinIdx === -1) {
            return '<span class="badge-silent">TYST 1H</span>';
        }
        const minsAgo = (BIN_COUNT - 1) - lastActiveBinIdx;
        if (minsAgo === 0) {
            return '<span class="last-now">NU</span>';
        }
        return `${minsAgo}m sen`;
    }

    function renderTimeTrack(ch) {
        if (!ch.total60m || ch.total60m === 0) {
            return '<div class="time-track-empty">INGA MEDDELANDEN MOTTAGNA SENASTE 60 MIN</div>';
        }

        let peakInMin = 1;
        for (let i = 0; i < BIN_COUNT; i++) {
            if (ch.bins[i].total > peakInMin) peakInMin = ch.bins[i].total;
        }
        const maxScale = Math.max(6, peakInMin);

        const now = new Date();
        let barsHtml = '';
        for (let i = 0; i < BIN_COUNT; i++) {
            const bin = ch.bins[i];
            const minutesAgo = (BIN_COUNT - 1) - i;
            const binTime = new Date(now.getTime() - minutesAgo * 60000);
            const timeStr = binTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            if (bin.total === 0) {
                barsHtml += `<div class="wf-bar heat-empty" title="0 msgs (${timeStr})"></div>`;
            } else {
                const h = Math.max(4, Math.min(22, Math.round((bin.total / maxScale) * 22)));
                let heatClass = 'heat-low';
                if (bin.total >= 6) {
                    heatClass = 'heat-burst';
                } else if (bin.total >= 3) {
                    heatClass = 'heat-med';
                }
                barsHtml += `<div class="wf-bar ${heatClass}" style="height: ${h}px;" title="${bin.total} msg${bin.total === 1 ? '' : 's'} (${timeStr})"></div>`;
            }
        }

        return `<div class="time-track">${barsHtml}</div>`;
    }

    function getSortedChannels() {
        const list = Object.values(channels);
        if (currentSort === 'silent') {
            // TYSTA (0) FÖRST
            list.sort((a, b) => {
                const aSilent = (a.total60m === 0) ? 0 : 1;
                const bSilent = (b.total60m === 0) ? 0 : 1;
                if (aSilent !== bSilent) return aSilent - bSilent;
                if (a.total60m !== b.total60m) return a.total60m - b.total60m;
                return a.name.localeCompare(b.name);
            });
        } else if (currentSort === 'freq') {
            // FREKVENS (numerisk sortering)
            list.sort((a, b) => {
                const fa = parseFloat(String(a.frequency).replace(/[^0-9.]/g, '')) || 0;
                const fb = parseFloat(String(b.frequency).replace(/[^0-9.]/g, '')) || 0;
                if (fa !== fb) return fa - fb;
                return a.name.localeCompare(b.name);
            });
        } else {
            // Standard: HÖGST -> 0 MSGS
            list.sort((a, b) => {
                if (b.total60m !== a.total60m) return b.total60m - a.total60m;
                return a.name.localeCompare(b.name);
            });
        }
        return list;
    }

    function updateSortButtonsUI() {
        const btnCount = document.getElementById('wfSortCount');
        const btnSilent = document.getElementById('wfSortSilent');
        const btnFreq = document.getElementById('wfSortFreq');

        if (btnCount) btnCount.classList.toggle('active', currentSort === 'count');
        if (btnSilent) btnSilent.classList.toggle('active', currentSort === 'silent');
        if (btnFreq) btnFreq.classList.toggle('active', currentSort === 'freq');
    }

    function setSort(mode) {
        if (!['count', 'silent', 'freq'].includes(mode)) return;
        currentSort = mode;
        localStorage.setItem('pagermonitor-wf-sort', mode);
        updateSortButtonsUI();
        renderChannelRows();
    }

    function updateHeaderKPIs() {
        const chList = Object.values(channels);
        let totalMsgs = 0;
        let activeCount = 0;
        const totalChannels = chList.length;

        chList.forEach(ch => {
            totalMsgs += (ch.total60m || 0);
            if (ch.total60m > 0) activeCount++;
        });

        const rate = (totalMsgs / 60).toFixed(1);

        const totalEl = document.getElementById('wfKpiTotal');
        const rateEl = document.getElementById('wfKpiRate');
        const activeEl = document.getElementById('wfKpiActive');

        if (totalEl) totalEl.textContent = `${totalMsgs} msgs`;
        if (rateEl) rateEl.textContent = `${rate} msg/min`;
        if (activeEl) activeEl.textContent = `${activeCount} / ${totalChannels}`;
    }

    function updateFilterUI() {
        Object.values(channels).forEach(ch => {
            const row = document.getElementById(`wf-row-${ch.id}`);
            const chk = document.getElementById(`check-${ch.id}`);
            const isSelected = activeFilterChannels.has(ch.id);

            if (row) row.classList.toggle('active-filter', isSelected);
            if (chk) chk.checked = isSelected;
        });

        const clearBtn = document.getElementById('ribbonClearFilterBtn');
        if (clearBtn) {
            if (activeFilterChannels.size > 0) {
                clearBtn.style.display = 'inline-flex';
                clearBtn.textContent = `[Rensa filter (${activeFilterChannels.size})]`;
            } else {
                clearBtn.style.display = 'none';
            }
        }
    }

    function renderChannelRows() {
        const container = document.getElementById('waterfallChannels');
        if (!container) return;

        updateHeaderKPIs();
        updateSortButtonsUI();

        const sortedList = getSortedChannels();
        let maxTotal = 1;
        sortedList.forEach(ch => {
            if (ch.total60m > maxTotal) maxTotal = ch.total60m;
        });

        container.innerHTML = '';

        sortedList.forEach(ch => {
            const isSelected = activeFilterChannels.has(ch.id);
            const protoInfo = detectChannelProtocol(ch);
            const isSilent = (ch.total60m === 0);
            const rateStr = (ch.total60m / 60).toFixed(1) + ' msg/m';
            const volPercent = Math.min(100, Math.round((ch.total60m / maxTotal) * 100));
            const lastSeenHtml = formatLastSeen(ch);
            const timeTrackHtml = renderTimeTrack(ch);

            const row = document.createElement('div');
            row.className = `ch-row ${protoInfo.borderCls} ${isSilent ? 'is-silent' : ''} ${isSelected ? 'active-filter' : ''}`;
            row.id = `wf-row-${ch.id}`;

            row.innerHTML = `
                <div class="wf-col-val" onclick="event.stopPropagation()">
                    <input type="checkbox" class="ch-checkbox" id="check-${ch.id}" ${isSelected ? 'checked' : ''} onchange="window.WaterfallManager.toggleChannelFilterById('${ch.id}')" title="${isSelected ? 'Avmarkera filter' : 'Filtrera på denna kanal'}">
                </div>
                <div class="wf-col-proto">
                    <span class="wf-proto-badge ${protoInfo.cls}">${protoInfo.name}</span>
                </div>
                <div class="wf-col-freq" title="${ch.frequency}">${ch.frequency}</div>
                <div class="wf-col-rx" title="${ch.name}">${ch.name}</div>
                <div class="wf-col-time">${timeTrackHtml}</div>
                <div class="wf-col-last">${lastSeenHtml}</div>
                <div class="wf-col-rate">${rateStr}</div>
                <div class="wf-col-vol">
                    <span class="vol-num">${ch.total60m} msgs</span>
                    <div class="vol-meter">
                        <div class="vol-meter-fill" style="width: ${volPercent}%;"></div>
                    </div>
                </div>
            `;

            row.addEventListener('click', () => {
                toggleChannelFilter(ch);
            });

            container.appendChild(row);
        });

        updateFilterUI();
    }

    function scheduleRender() {
        if (renderDebounceTimer) return;
        renderDebounceTimer = setTimeout(() => {
            renderDebounceTimer = null;
            renderChannelRows();
        }, 80);
    }

    function toggleChannelFilter(ch) {
        if (!ch || !ch.id) return;
        if (activeFilterChannels.has(ch.id)) {
            activeFilterChannels.delete(ch.id);
        } else {
            activeFilterChannels.add(ch.id);
        }

        updateFilterUI();

        if (onFilterCallback) {
            onFilterCallback(activeFilterChannels);
        }
    }

    function toggleChannelFilterById(channelId) {
        const ch = channels[channelId];
        if (ch) {
            toggleChannelFilter(ch);
        }
    }

    function clearAllFilters() {
        activeFilterChannels.clear();
        updateFilterUI();
        if (onFilterCallback) {
            onFilterCallback(activeFilterChannels);
        }
    }

    function hasActiveFilter() {
        return activeFilterChannels.size > 0;
    }

    function getActiveFilters() {
        return Array.from(activeFilterChannels);
    }

    function isRowMatchingFilter(tr) {
        if (!tr || activeFilterChannels.size === 0) return true;

        // 1. Snabb matchning via data-channel-key
        const chKey = tr.getAttribute('data-channel-key') || (tr.dataset ? tr.dataset.channelKey : '');
        if (chKey && activeFilterChannels.has(chKey)) {
            return true;
        }

        // 2. Extrahera frekvens och protokoll ur data-attribut eller child badges
        let rawFreq = tr.getAttribute('data-frequency') || (tr.dataset ? tr.dataset.frequency : '');
        let rawProto = tr.getAttribute('data-protocol') || (tr.dataset ? tr.dataset.protocol : '');
        let rawBitrate = tr.getAttribute('data-bitrate') || (tr.dataset ? tr.dataset.bitrate : '');

        if (!rawFreq) {
            const freqBadge = tr.querySelector('.badge-freq, .rf-freq');
            if (freqBadge) rawFreq = freqBadge.textContent || '';
        }
        if (!rawProto) {
            const protoBadge = tr.querySelector('.badge-proto, .badge');
            if (protoBadge) rawProto = protoBadge.textContent || '';
        }

        const rowNormFreq = normalizeFrequency(rawFreq);
        const rowProtoUpper = (rawProto || '').toUpperCase();
        const rowBitrateUpper = (rawBitrate || '').toUpperCase();

        for (const actKey of activeFilterChannels) {
            const ch = channels[actKey];
            if (!ch) continue;

            // Om aktiv kanal är RDS
            const isChRds = (ch.name && (ch.name.toUpperCase() === 'RDS' || ch.name.toUpperCase().includes('RDS') || ch.name.toUpperCase().includes('TMC')));
            if (isChRds) {
                if (rowProtoUpper.includes('RDS') || rowProtoUpper.includes('TMC') || rowBitrateUpper.includes('RDS') || rowBitrateUpper.includes('TMC')) {
                    return true;
                }
            }

            // Normaliserad numerisk frekvensmatchning
            const chNormFreq = normalizeFrequency(ch.frequency);
            if (chNormFreq && chNormFreq !== 'Unknown' && chNormFreq !== 'auto' && rowNormFreq && rowNormFreq !== 'Unknown') {
                if (chNormFreq === rowNormFreq) {
                    return true;
                }
            }

            // Fallback mot delsträngsmatchning i frekvenstext
            if (rawFreq && ch.frequency && ch.frequency !== 'auto' && ch.frequency !== 'Unknown') {
                const cleanCh = ch.frequency.replace(/MHz|M|Hz/gi, '').trim();
                const cleanRow = rawFreq.replace(/MHz|M|Hz/gi, '').trim();
                if (cleanCh && (cleanRow === cleanCh || cleanRow.startsWith(cleanCh) || cleanCh.startsWith(cleanRow))) {
                    return true;
                }
            }
        }

        return false;
    }

    function getChannelKeyForMessage(msg) {
        if (!msg) return null;
        const freq = msg.frequency || 'Unknown';
        if (freq === 'RESTART' || freq === 'Unknown') return null;

        const isRdsMsg = (msg.bitrate && (msg.bitrate.includes('RDS') || msg.bitrate.includes('TMC'))) || 
                         (msg.protocol && msg.protocol.includes('RDS')) ||
                         (msg.sdr_name && msg.sdr_name.toUpperCase().includes('RDS'));
        if (isRdsMsg) {
            const rdsKey = Object.keys(channels).find(k => channels[k].name && (channels[k].name.toUpperCase() === 'RDS' || channels[k].name.toUpperCase().includes('RDS')));
            if (rdsKey) return rdsKey;
        }

        return getChannelKey(freq);
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

        const isSondeMsg = (msg.protocol && msg.protocol.toUpperCase().includes('SONDE')) ||
                           (msg.bitrate && msg.bitrate.toUpperCase().includes('SONDE')) ||
                           (msg.sdr_name && (msg.sdr_name.toUpperCase().includes('SONDE') || msg.sdr_name.toUpperCase().includes('RADIO'))) ||
                           (msg.alias && (msg.alias.toUpperCase().includes('RS41') || msg.alias.toUpperCase().includes('DFM') || msg.alias.toUpperCase().includes('SONDE')));

        const isVdl2Msg = (msg.protocol && msg.protocol.toUpperCase().includes('VDL')) ||
                          (msg.bitrate && msg.bitrate.toUpperCase().includes('VDL')) ||
                          (msg.sdr_name && msg.sdr_name.toUpperCase().includes('VDL'));

        const isSatcMsg = (msg.protocol && (msg.protocol.toUpperCase().includes('SATC') || msg.protocol.toUpperCase().includes('INMARSAT'))) ||
                          (msg.bitrate && (msg.bitrate.toUpperCase().includes('SATC') || msg.bitrate.toUpperCase().includes('INMARSAT'))) ||
                          (msg.sdr_name && (msg.sdr_name.toUpperCase().includes('SATC') || msg.sdr_name.toUpperCase().includes('INMARSAT')));

        const isHfdlMsg = (msg.protocol && msg.protocol.toUpperCase().includes('HFDL')) ||
                          (msg.bitrate && msg.bitrate.toUpperCase().includes('HFDL')) ||
                          (msg.sdr_name && msg.sdr_name.toUpperCase().includes('HFDL'));

        let ch = null;
        if (isRdsMsg) {
            const rdsKey = Object.keys(channels).find(k => channels[k].name && (channels[k].name.toUpperCase() === 'RDS' || channels[k].name.toUpperCase().includes('RDS')));
            if (rdsKey) {
                ch = channels[rdsKey];
                if (freq && freq !== 'Unknown' && ch.frequency.toLowerCase() === 'auto') {
                    ch.frequency = freq;
                }
            }
        }

        if (!ch) {
            let sdrName = msg.sdr_name;
            let proto = msg.protocol;
            if (!sdrName) {
                if (isSondeMsg) {
                    sdrName = `Radiosond ${freq}`;
                    proto = 'SONDE';
                } else if (isVdl2Msg) {
                    sdrName = `VDL2 ${freq}`;
                    proto = 'VDL2';
                } else if (isSatcMsg) {
                    sdrName = `Inmarsat ${freq}`;
                    proto = 'SAT-C';
                } else if (isHfdlMsg) {
                    sdrName = `HFDL ${freq}`;
                    proto = 'HFDL';
                } else {
                    sdrName = msg.frequency ? `Freq ${msg.frequency}` : 'Receiver';
                }
            }
            ch = registerChannel(sdrName, freq, proto);
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
            ch.lastSeen = now;

            scheduleRender();
        }
    }

    function rollTimeline() {
        Object.values(channels).forEach(ch => {
            ch.bins.shift();
            ch.bins.push({ total: 0, alerts: 0, duplicates: 0 });
            ch.total60m = ch.bins.reduce((sum, b) => sum + b.total, 0);
        });

        renderChannelRows();
    }

    function toggleCollapse() {
        const panel = document.getElementById('activityRibbonPanel');
        const indicator = document.getElementById('wfCollapseIndicator');
        if (!panel) return;

        isCollapsed = !isCollapsed;
        panel.classList.toggle('collapsed', isCollapsed);

        if (indicator) {
            indicator.textContent = isCollapsed ? '[v VISA]' : '[^ DÖLJ]';
        }

        localStorage.setItem('pagermonitor-ribbon-collapsed', isCollapsed ? 'true' : 'false');

        if (!isCollapsed) {
            renderChannelRows();
        }
    }

    async function init(initialMessages = [], filterCallback = null) {
        onFilterCallback = filterCallback;

        // Default to COLLAPSED (true) unless user explicitly saved 'false'
        const savedCollapsed = localStorage.getItem('pagermonitor-ribbon-collapsed');
        const shouldCollapse = (savedCollapsed === null) ? true : (savedCollapsed === 'true');
        
        isCollapsed = shouldCollapse;
        const panel = document.getElementById('activityRibbonPanel');
        const indicator = document.getElementById('wfCollapseIndicator');
        if (panel) panel.classList.toggle('collapsed', isCollapsed);
        if (indicator) {
            indicator.textContent = isCollapsed ? '[v VISA]' : '[^ DÖLJ]';
        }

        // Fetch configured SDR instances
        try {
            const res = await fetch('/api/sdr');
            if (res.ok) {
                sdrInstances = await res.json();
                sdrInstances.forEach(inst => {
                    if (inst.enabled) {
                        registerChannel(inst.name, inst.frequency, inst.protocol);
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

        // Roll timer: check every 15s if minute changed
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
        setSort: setSort,
        toggleChannelFilter: toggleChannelFilter,
        toggleChannelFilterById: toggleChannelFilterById,
        clearAllFilters: clearAllFilters,
        hasActiveFilter: hasActiveFilter,
        getActiveFilters: getActiveFilters,
        isRowMatchingFilter: isRowMatchingFilter,
        getChannelKeyForMessage: getChannelKeyForMessage,
        renderChannelRows: renderChannelRows,
        drawAllCanvases: function () {}
    };
})();
