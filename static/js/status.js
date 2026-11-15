// "Live from the server": CPU, memory, per-step timings and the latest traced
// detection, read from /api/status (Prometheus + Tempo behind the website).
// The section stays hidden when monitoring is not connected.
(() => {
    const REFRESH_MS = 30000;
    const section = document.getElementById('live');
    if (!section) return;
    const tip = document.getElementById('viz-tip');

    const SPAN_LABELS = {
        'POST /api/inference': 'Website handles the request',
        'POST': 'Website calls the detector',
        'POST /predict': 'Detector handles the request',
        'inference.pipeline': 'Detection pipeline',
        'inference.validate': 'Check the box size',
        'inference.detect': 'Download tiles and run the model',
        'inference.postprocess': 'Build the GeoJSON result',
    };
    const STAGE_LABELS = {
        validate: 'Check the box',
        detect: 'Tiles + model',
        postprocess: 'Build result',
    };

    const el = (tag, cls, text) => {
        const node = document.createElement(tag);
        if (cls) node.className = cls;
        if (text !== undefined) node.textContent = text;
        return node;
    };
    const num = (n, digits = 0) =>
        n.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
    const gb = (bytes) => bytes / 1024 ** 3;
    const mb = (bytes) => bytes / 1024 ** 2;

    function duration(ms) {
        if (ms < 1) return '< 1 ms';
        if (ms < 1000) return `${num(ms)} ms`;
        return `${num(ms / 1000, ms < 10000 ? 2 : 1)} s`;
    }

    function ago(seconds) {
        const s = Math.max(0, Date.now() / 1000 - seconds);
        if (s < 90) return 'just now';
        if (s < 5400) return `${Math.round(s / 60)} minutes ago`;
        if (s < 129600) return `${Math.round(s / 3600)} hours ago`;
        return `${Math.round(s / 86400)} days ago`;
    }

    // One shared tooltip for every mark in the section.
    function attachTip(node, lines) {
        node.tabIndex = 0;
        const show = (x, y) => {
            tip.replaceChildren(...lines().map((line, i) => el('div', i === 0 ? 'viz-tip-title' : '', line)));
            tip.hidden = false;
            const box = section.getBoundingClientRect();
            const left = Math.min(Math.max(8, x - box.left + 12), box.width - tip.offsetWidth - 8);
            tip.style.left = `${left}px`;
            tip.style.top = `${y - box.top + 14}px`;
        };
        node.addEventListener('pointermove', (e) => show(e.clientX, e.clientY));
        node.addEventListener('pointerleave', () => (tip.hidden = true));
        node.addEventListener('focus', () => {
            const r = node.getBoundingClientRect();
            show(r.left, r.bottom - 8);
        });
        node.addEventListener('blur', () => (tip.hidden = true));
    }

    // 0-100% line over the last hour; hover reads the nearest sample.
    function sparkline(points, label) {
        const W = 240, H = 28;
        const wrap = el('div', 'spark');
        if (!points || points.length < 2) return wrap;
        const t0 = points[0][0], t1 = points[points.length - 1][0];
        const x = (t) => ((t - t0) / (t1 - t0 || 1)) * W;
        const y = (v) => H - 2 - (Math.min(100, Math.max(0, v)) / 100) * (H - 4);
        const ns = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(ns, 'svg');
        svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
        svg.setAttribute('preserveAspectRatio', 'none');
        svg.setAttribute('role', 'img');
        svg.setAttribute('aria-label', `${label} over the last hour, on a 0 to 100% scale`);
        const base = document.createElementNS(ns, 'line');
        base.setAttribute('class', 'spark-base');
        base.setAttribute('x1', 0); base.setAttribute('x2', W);
        base.setAttribute('y1', H - 1); base.setAttribute('y2', H - 1);
        const line = document.createElementNS(ns, 'polyline');
        line.setAttribute('class', 'spark-line');
        line.setAttribute('points', points.map(([t, v]) => `${x(t).toFixed(1)},${y(v).toFixed(1)}`).join(' '));
        const dot = document.createElementNS(ns, 'circle');
        dot.setAttribute('class', 'spark-dot');
        dot.setAttribute('r', 3);
        dot.style.display = 'none';
        svg.append(base, line, dot);
        wrap.append(svg, el('span', 'spark-note', 'last hour, 0–100%'));

        let nearest = points[points.length - 1];
        svg.addEventListener('pointermove', (e) => {
            const r = svg.getBoundingClientRect();
            const t = t0 + ((e.clientX - r.left) / r.width) * (t1 - t0);
            nearest = points.reduce((a, b) => (Math.abs(b[0] - t) < Math.abs(a[0] - t) ? b : a));
            dot.setAttribute('cx', x(nearest[0]));
            dot.setAttribute('cy', y(nearest[1]));
            dot.style.display = '';
        });
        svg.addEventListener('pointerleave', () => (dot.style.display = 'none'));
        attachTip(svg, () => [
            `${label}: ${num(nearest[1], 1)}%`,
            new Date(nearest[0] * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        ]);
        return wrap;
    }

    // A tile: label, big value, optional 0-100% bar, a line of detail, optional sparkline.
    function tile({ label, value, unit, percent, peak, peakText, detail, history, tip }) {
        const box = el('div', 'tile');
        const val = el('div', 'tile-value', value);
        if (unit) val.append(el('small', '', unit));
        box.append(el('div', 'tile-label', label), val);
        if (percent != null) {
            const track = el('div', 'meter-track');
            const fill = el('div', 'meter-fill');
            fill.style.width = `${Math.min(100, Math.max(0, percent))}%`;
            track.append(fill);
            if (peak != null) {
                const mark = el('div', 'meter-peak');
                mark.style.left = `${Math.min(100, Math.max(0, peak))}%`;
                track.append(mark);
            }
            track.setAttribute('role', 'meter');
            track.setAttribute('aria-label', label);
            track.setAttribute('aria-valuemin', 0);
            track.setAttribute('aria-valuemax', 100);
            track.setAttribute('aria-valuenow', Math.round(percent));
            box.append(track);
        }
        if (detail) box.append(el('p', 'tile-detail', detail));
        if (peakText) {
            const line = el('p', 'tile-peak');
            line.append(el('span', 'peak-key'), el('span', '', peakText));
            box.append(line);
        }
        if (history) box.append(sparkline(history, label));
        if (tip) attachTip(box, tip);
        return box;
    }

    function renderServer(data) {
        const n = data.node;
        const l = data.latency;
        const tiles = document.getElementById('live-tiles');
        tiles.replaceChildren();
        const days = data.window.replace('d', '');
        const parts = [];
        if (n.cpu_cores) parts.push(`${num(n.cpu_cores)} vCPU`);
        if (n.memory_total_bytes) parts.push(`${num(gb(n.memory_total_bytes), 1)} GB memory`);
        parts.push('one k3s node on Oracle Cloud');
        document.getElementById('live-server-sub').textContent = parts.join(' · ');

        if (n.cpu_percent != null) {
            tiles.append(tile({
                label: 'CPU', value: `${num(n.cpu_percent)}%`, percent: n.cpu_percent,
                detail: 'average over 5 minutes', history: data.history.cpu_percent,
                peak: n.cpu_peak_percent,
                peakText: n.cpu_peak_percent != null ? `Peak ${num(n.cpu_peak_percent)}% in the last ${days} days` : null,
            }));
        }
        if (n.memory_used_bytes != null && n.memory_total_bytes) {
            const percent = (100 * n.memory_used_bytes) / n.memory_total_bytes;
            tiles.append(tile({
                label: 'Memory', value: `${num(percent)}%`, percent,
                detail: `${num(gb(n.memory_used_bytes), 1)} of ${num(gb(n.memory_total_bytes), 1)} GB in use`,
                history: data.history.memory_percent,
                peak: n.memory_peak_bytes != null ? (100 * n.memory_peak_bytes) / n.memory_total_bytes : null,
                peakText: n.memory_peak_bytes != null
                    ? `Peak ${num(gb(n.memory_peak_bytes), 1)} GB (${num((100 * n.memory_peak_bytes) / n.memory_total_bytes)}%) in the last ${days} days` : null,
            }));
        }
        if (n.disk_used_bytes != null && n.disk_total_bytes) {
            const percent = (100 * n.disk_used_bytes) / n.disk_total_bytes;
            tiles.append(tile({
                label: 'Disk', value: `${num(percent)}%`, percent,
                detail: `${num(gb(n.disk_used_bytes), 1)} of ${num(gb(n.disk_total_bytes))} GB in use`,
                peak: n.disk_peak_bytes != null ? (100 * n.disk_peak_bytes) / n.disk_total_bytes : null,
                peakText: n.disk_peak_bytes != null
                    ? `Peak ${num(gb(n.disk_peak_bytes), 1)} GB (${num((100 * n.disk_peak_bytes) / n.disk_total_bytes)}%) in the last ${days} days` : null,
            }));
        }
        if (l.request_p50_seconds != null) {
            const count = l.detections != null ? Math.round(l.detections) : null;
            tiles.append(tile({
                label: 'A detection takes', value: duration(l.request_p50_seconds * 1000), unit: 'typically',
                detail: (l.request_p95_seconds != null ? `slowest 5%: ${duration(l.request_p95_seconds * 1000)} · ` : '')
                    + `last ${days} days` + (count ? `, ${num(count)} detections` : ''),
            }));
        }
    }

    function renderPods(pods) {
        const box = document.getElementById('live-pods');
        box.replaceChildren();
        pods.forEach((pod) => {
            const used = mb(pod.memory_bytes);
            const limit = pod.memory_limit_bytes ? mb(pod.memory_limit_bytes) : null;
            // millicores: 1000m is one full core
            const cpu = `CPU ${num(pod.cpu_cores * 1000)}m`;
            box.append(tile({
                label: pod.name,
                value: num(used),
                unit: limit ? `of ${num(limit)} MB` : 'MB',
                percent: limit ? (100 * used) / limit : null,
                detail: cpu,
                tip: () => [
                    pod.name,
                    limit ? `${num(used)} MB of its ${num(limit)} MB limit (${num((100 * used) / limit)}%)` : `${num(used)} MB`,
                    `${cpu}: 1000m is one full CPU core`,
                ],
            }));
        });
    }

    function renderStages(latency, window) {
        const days = window.replace('d', '');
        const count = latency.detections != null ? Math.round(latency.detections) : null;
        document.getElementById('live-stages-sub').textContent =
            `95th percentile over the last ${days} days` + (count ? `, from ${num(count)} detections` : '');
        const box = document.getElementById('live-stages');
        box.replaceChildren();
        if (!latency.stages.length) {
            box.append(el('p', 'live-empty', 'No detections in this period yet.'));
            return;
        }
        const max = Math.max(...latency.stages.map((s) => s.p95_seconds));
        latency.stages.forEach((s) => {
            // The histogram's smallest bucket is 50 ms, so anything faster reads as "under 50 ms".
            const text = s.p95_seconds < 0.05 ? 'under 50 ms' : duration(s.p95_seconds * 1000);
            const row = el('div', 'hbar-row');
            const track = el('div', 'hbar-track');
            const bar = el('div', 'hbar');
            bar.style.width = `${Math.max(0.6, (100 * s.p95_seconds) / max)}%`;
            track.append(bar);
            row.append(el('span', 'hbar-label', STAGE_LABELS[s.stage] || s.stage), track, el('span', 'hbar-value', text));
            attachTip(row, () => [STAGE_LABELS[s.stage] || s.stage, `p95: ${text}`, `stage "${s.stage}" in the detector`]);
            box.append(row);
        });
    }

    function renderTrace(trace) {
        const box = document.getElementById('live-trace');
        const sub = document.getElementById('live-trace-sub');
        box.replaceChildren();
        if (!trace || !trace.spans.length) {
            sub.textContent = 'Where the time went';
            box.append(el('p', 'live-empty', 'No detection has been traced in the last 7 days. Draw a box above to make one.'));
            return;
        }
        const facts = [`${duration(trace.duration_ms)} in total`];
        if (trace.area_m2 != null) facts.push(`${num(trace.area_m2 / 1e6, 2)} km²`);
        if (trace.tiles != null) facts.push(`${num(trace.tiles)} map tiles`);
        if (trace.detections != null) facts.push(`${num(trace.detections)} trees found`);
        facts.push(ago(trace.started_at));
        sub.textContent = facts.join(' · ');

        const total = trace.duration_ms || 1;
        trace.spans.forEach((span) => {
            const isWeb = span.service === 'cocolit-frontend';
            const label = SPAN_LABELS[span.name] || span.name;
            const row = el('div', 'trace-row');
            const name = el('div', 'trace-name');
            name.style.paddingLeft = `${span.depth * 0.75}rem`;
            name.append(el('span', 'trace-label', label), el('code', 'trace-raw', span.name));
            const lane = el('div', 'trace-lane');
            const bar = el('div', `trace-bar ${isWeb ? 'is-web' : 'is-det'}`);
            bar.style.left = `${(100 * span.start_ms) / total}%`;
            bar.style.width = `${Math.max(0.4, (100 * span.duration_ms) / total)}%`;
            lane.append(bar);
            row.append(name, lane, el('span', 'trace-time', duration(span.duration_ms)));
            attachTip(row, () => [
                label,
                `${isWeb ? 'Website' : 'Detector'} · span "${span.name}"`,
                `took ${duration(span.duration_ms)}, started at ${duration(span.start_ms)}`,
            ]);
            box.append(row);
        });
        const axis = el('div', 'trace-row trace-axis');
        const ticks = el('div', 'trace-lane trace-ticks');
        ticks.append(el('span', '', '0'), el('span', '', duration(total / 2)), el('span', '', duration(total)));
        axis.append(el('div', 'trace-name'), ticks, el('span', 'trace-time'));
        box.append(axis);
    }

    async function refresh() {
        try {
            const response = await fetch('/api/status');
            if (!response.ok) throw new Error(`status ${response.status}`);
            const data = await response.json();
            if (!data.available) {
                section.hidden = true;
                const nav = document.getElementById('live-nav');
                if (nav) nav.hidden = true;
                return;
            }
            renderServer(data);
            renderPods(data.pods);
            renderStages(data.latency, data.window);
            renderTrace(data.trace);
            document.getElementById('live-updated').textContent =
                `Updated ${new Date(data.updated_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}, refreshes every 30 seconds.`;
            section.hidden = false;
            const nav = document.getElementById('live-nav');
            if (nav) nav.hidden = false;
        } catch (err) {
            console.error('Failed to load server status:', err);
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        refresh();
        setInterval(() => {
            if (!document.hidden) refresh();
        }, REFRESH_MS);
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) refresh();
        });
    });
})();
