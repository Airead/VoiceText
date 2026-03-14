"""Statistics visualization panel with interactive charts via WKWebView + Chart.js."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from voicetext.usage_stats import UsageStats

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Close delegate (lazy-created to avoid PyObjC import at module level)
# ---------------------------------------------------------------------------
_PanelCloseDelegate = None


def _get_panel_close_delegate_class():
    global _PanelCloseDelegate
    if _PanelCloseDelegate is None:
        from Foundation import NSObject

        class StatsChartCloseDelegate(NSObject):
            _panel_ref = None

            def windowWillClose_(self, notification):
                if self._panel_ref is not None:
                    self._panel_ref.close()

        _PanelCloseDelegate = StatsChartCloseDelegate
    return _PanelCloseDelegate


# ---------------------------------------------------------------------------
# HTML template with embedded Chart.js
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
:root {
    --bg: #ffffff; --text: #1d1d1f; --card-bg: #f5f5f7;
    --border: #d2d2d7; --secondary: #86868b; --accent: #007aff;
    --green: #34c759; --orange: #ff9500; --red: #ff3b30;
    --purple: #af52de; --teal: #5ac8fa; --pink: #ff2d55;
}
@media (prefers-color-scheme: dark) {
    :root {
        --bg: #1d1d1f; --text: #f5f5f7; --card-bg: #2c2c2e;
        --border: #48484a; --secondary: #98989d; --accent: #0a84ff;
        --green: #30d158; --orange: #ff9f0a; --red: #ff453a;
        --purple: #bf5af2; --teal: #64d2ff; --pink: #ff375f;
    }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
    background: var(--bg); color: var(--text);
    padding: 20px; overflow-y: auto;
}
.cards-row {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
    margin-bottom: 20px;
}
.card {
    background: var(--card-bg); border-radius: 10px; padding: 16px;
    border: 1px solid var(--border);
}
.card .label { font-size: 12px; color: var(--secondary); margin-bottom: 4px; }
.card .value { font-size: 28px; font-weight: 600; }
.card .sub { font-size: 11px; color: var(--secondary); margin-top: 4px; }
.chart-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
}
.chart-container {
    background: var(--card-bg); border-radius: 10px; padding: 16px;
    border: 1px solid var(--border);
}
.chart-container h3 {
    font-size: 14px; font-weight: 600; margin-bottom: 12px;
}
.chart-wrap {
    position: relative; height: 250px;
}
.empty-hint {
    color: var(--secondary); font-size: 13px; text-align: center;
    padding-top: 80px;
}
.tab-bar {
    display: flex; gap: 8px; margin-bottom: 16px;
}
.tab-btn {
    background: var(--card-bg); border: 1px solid var(--border);
    border-radius: 6px; padding: 6px 14px; cursor: pointer;
    font-size: 13px; color: var(--text); font-family: inherit;
}
.tab-btn.active {
    background: var(--accent); color: #fff; border-color: var(--accent);
}
</style>
</head>
<body>

<div class="cards-row" id="cards"></div>

<div class="tab-bar">
    <button class="tab-btn active" onclick="setRange(7)">7 Days</button>
    <button class="tab-btn" onclick="setRange(14)">14 Days</button>
    <button class="tab-btn" onclick="setRange(30)">30 Days</button>
</div>

<div class="chart-grid">
    <div class="chart-container">
        <h3>Daily Transcriptions</h3>
        <div class="chart-wrap"><canvas id="dailyTrend"></canvas></div>
    </div>
    <div class="chart-container">
        <h3>Mode Distribution</h3>
        <div class="chart-wrap"><canvas id="modePie"></canvas></div>
    </div>
    <div class="chart-container">
        <h3>Token Usage</h3>
        <div class="chart-wrap"><canvas id="tokenArea"></canvas></div>
    </div>
    <div class="chart-container">
        <h3>Enhance Modes</h3>
        <div class="chart-wrap"><canvas id="enhanceBar"></canvas></div>
    </div>
</div>

<script>
const DATA = __STATS_DATA__;

const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
Chart.defaults.color = isDark ? '#f5f5f7' : '#1d1d1f';
Chart.defaults.borderColor = isDark ? 'rgba(72,72,74,0.5)' : 'rgba(210,210,215,0.5)';
Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif';
Chart.defaults.font.size = 12;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;

const COLORS = {
    accent: isDark ? '#0a84ff' : '#007aff',
    green: isDark ? '#30d158' : '#34c759',
    orange: isDark ? '#ff9f0a' : '#ff9500',
    red: isDark ? '#ff453a' : '#ff3b30',
    purple: isDark ? '#bf5af2' : '#af52de',
    teal: isDark ? '#64d2ff' : '#5ac8fa',
    pink: isDark ? '#ff375f' : '#ff2d55',
};

// --- Summary Cards ---
function renderCards() {
    const cum = DATA.cumulative;
    const today = DATA.today;
    const t = cum.totals || {};
    const td = today.totals || {};
    const tk = cum.token_usage || {};

    const cards = [
        { label: 'Total Transcriptions', value: t.transcriptions || 0,
          sub: `Today: ${td.transcriptions || 0}` },
        { label: 'Total Tokens', value: formatNum(tk.total_tokens || 0),
          sub: `\u2191${formatNum(tk.prompt_tokens || 0)} \u2193${formatNum(tk.completion_tokens || 0)}` },
        { label: 'Accept Rate',
          value: calcRate(t.direct_accept, t.direct_accept + t.user_modification + t.cancel),
          sub: `Accept: ${t.direct_accept || 0} | Modified: ${t.user_modification || 0}` },
        { label: 'Days Active', value: DATA.daily.filter(d => (d.totals||{}).transcriptions > 0).length,
          sub: cum.first_recorded ? `Since ${cum.first_recorded.slice(0, 10)}` : 'No data yet' },
    ];

    const container = document.getElementById('cards');
    container.innerHTML = cards.map(c => `
        <div class="card">
            <div class="label">${c.label}</div>
            <div class="value">${c.value}</div>
            <div class="sub">${c.sub}</div>
        </div>
    `).join('');
}

function formatNum(n) {
    return n.toLocaleString();
}

function calcRate(num, denom) {
    if (!denom) return '-';
    return Math.round(num / denom * 100) + '%';
}

// --- Charts ---
let currentRange = 7;
let chartInstances = {};

function setRange(days) {
    currentRange = days;
    document.querySelectorAll('.tab-btn').forEach((btn, i) => {
        btn.classList.toggle('active', [7,14,30][i] === days);
    });
    renderCharts();
}

function getSlicedDaily() {
    return DATA.daily.slice(-currentRange);
}

function renderCharts() {
    const daily = getSlicedDaily();
    const labels = daily.map(d => {
        const parts = (d.date || '').split('-');
        return parts.length === 3 ? parts[1] + '/' + parts[2] : d.date;
    });

    // Daily Trend
    destroyChart('dailyTrend');
    chartInstances.dailyTrend = new Chart(document.getElementById('dailyTrend'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Transcriptions',
                data: daily.map(d => (d.totals||{}).transcriptions || 0),
                borderColor: COLORS.accent,
                backgroundColor: COLORS.accent + '33',
                fill: true, tension: 0.3, pointRadius: 3, pointHoverRadius: 6,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            scales: {
                y: { beginAtZero: true, ticks: { precision: 0 } },
            },
            plugins: { legend: { display: false } },
        }
    });

    // Mode Pie
    destroyChart('modePie');
    const cum = DATA.cumulative.totals || {};
    const pieData = [
        cum.direct_mode || 0, cum.preview_mode || 0
    ];
    const actionData = [
        cum.direct_accept || 0, cum.user_modification || 0, cum.cancel || 0
    ];
    const hasPie = pieData.some(v => v > 0) || actionData.some(v => v > 0);

    if (hasPie) {
        chartInstances.modePie = new Chart(document.getElementById('modePie'), {
            type: 'doughnut',
            data: {
                labels: ['Direct', 'Preview', 'Accept', 'Modified', 'Cancel'],
                datasets: [
                    {
                        label: 'Input Mode',
                        data: [...pieData, 0, 0, 0],
                        backgroundColor: [COLORS.accent, COLORS.green, 'transparent', 'transparent', 'transparent'],
                        weight: 1,
                    },
                    {
                        label: 'User Action',
                        data: [0, 0, ...actionData],
                        backgroundColor: ['transparent', 'transparent', COLORS.teal, COLORS.orange, COLORS.red],
                        weight: 1,
                    }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                cutout: '40%',
                plugins: {
                    legend: { position: 'bottom', labels: {
                        generateLabels: function(chart) {
                            const ds0 = chart.data.datasets[0];
                            const ds1 = chart.data.datasets[1];
                            const items = [];
                            const mapping = [
                                { idx: 0, ds: 0, text: 'Direct',   val: cum.direct_mode },
                                { idx: 1, ds: 0, text: 'Preview',  val: cum.preview_mode },
                                { idx: 2, ds: 1, text: 'Accept',   val: cum.direct_accept },
                                { idx: 3, ds: 1, text: 'Modified', val: cum.user_modification },
                                { idx: 4, ds: 1, text: 'Cancel',   val: cum.cancel },
                            ];
                            mapping.forEach(m => {
                                if (m.val > 0) {
                                    const src = m.ds === 0 ? ds0 : ds1;
                                    items.push({
                                        text: m.text,
                                        fillStyle: src.backgroundColor[m.idx],
                                        strokeStyle: src.backgroundColor[m.idx],
                                        lineWidth: 0,
                                        pointStyle: 'circle',
                                        datasetIndex: m.ds,
                                        index: m.idx,
                                    });
                                }
                            });
                            return items;
                        }
                    }},
                    tooltip: {
                        callbacks: {
                            label: ctx => {
                                const v = ctx.raw;
                                if (!v) return null;
                                return `${ctx.label}: ${v}`;
                            }
                        }
                    }
                },
            }
        });
    } else {
        document.getElementById('modePie').closest('.chart-container').innerHTML =
            '<h3>Mode Distribution</h3><div class="empty-hint">No data yet</div>';
    }

    // Token Area
    destroyChart('tokenArea');
    const hasTokens = daily.some(d => (d.token_usage||{}).total_tokens > 0);
    if (hasTokens) {
        chartInstances.tokenArea = new Chart(document.getElementById('tokenArea'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Prompt',
                        data: daily.map(d => (d.token_usage||{}).prompt_tokens || 0),
                        borderColor: COLORS.purple,
                        backgroundColor: COLORS.purple + '44',
                        fill: true, tension: 0.3, pointRadius: 2,
                    },
                    {
                        label: 'Completion',
                        data: daily.map(d => (d.token_usage||{}).completion_tokens || 0),
                        borderColor: COLORS.teal,
                        backgroundColor: COLORS.teal + '44',
                        fill: true, tension: 0.3, pointRadius: 2,
                    }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                scales: {
                    y: { beginAtZero: true, stacked: true },
                    x: {}
                },
                plugins: { legend: { position: 'bottom' } },
            }
        });
    } else {
        document.getElementById('tokenArea').closest('.chart-container').innerHTML =
            '<h3>Token Usage</h3><div class="empty-hint">No token data yet</div>';
    }

    // Enhance Mode Bar
    destroyChart('enhanceBar');
    const em = DATA.cumulative.enhance_mode_usage || {};
    const emKeys = Object.keys(em).sort((a, b) => em[b] - em[a]);
    if (emKeys.length > 0) {
        const barColors = [COLORS.accent, COLORS.green, COLORS.orange, COLORS.purple,
                           COLORS.teal, COLORS.pink, COLORS.red];
        chartInstances.enhanceBar = new Chart(document.getElementById('enhanceBar'), {
            type: 'bar',
            data: {
                labels: emKeys,
                datasets: [{
                    label: 'Usage Count',
                    data: emKeys.map(k => em[k]),
                    backgroundColor: emKeys.map((_, i) => barColors[i % barColors.length] + 'cc'),
                    borderColor: emKeys.map((_, i) => barColors[i % barColors.length]),
                    borderWidth: 1, borderRadius: 4,
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                indexAxis: emKeys.length > 5 ? 'y' : 'x',
                scales: {
                    [emKeys.length > 5 ? 'x' : 'y']: { beginAtZero: true, ticks: { precision: 0 } },
                },
                plugins: { legend: { display: false } },
            }
        });
    } else {
        document.getElementById('enhanceBar').closest('.chart-container').innerHTML =
            '<h3>Enhance Modes</h3><div class="empty-hint">No enhance mode data yet</div>';
    }
}

function destroyChart(id) {
    if (chartInstances[id]) {
        chartInstances[id].destroy();
        chartInstances[id] = null;
    }
}

// --- Init ---
renderCards();
renderCharts();
</script>
</body>
</html>"""


def build_stats_payload(
    usage_stats: UsageStats,
    days: int = 30,
) -> Dict[str, Any]:
    """Collect cumulative, today, and daily stats into a single dict."""
    cumulative = usage_stats.get_stats()
    today = usage_stats.get_today_stats()
    daily = get_daily_range(usage_stats, days)
    return {
        "cumulative": cumulative,
        "today": today,
        "daily": daily,
    }


def get_daily_range(
    usage_stats: UsageStats,
    days: int = 30,
) -> List[Dict[str, Any]]:
    """Return daily stats for the last *days* days, sorted chronologically."""
    today = date.today()
    result = []
    for i in range(days - 1, -1, -1):
        day_str = (today - timedelta(days=i)).isoformat()
        # Access internals through the lock-protected _load_daily
        with usage_stats._lock:
            data = usage_stats._load_daily(day_str)
        result.append(data)
    return result


def build_html(payload: Dict[str, Any]) -> str:
    """Build the final HTML by injecting the JSON payload into the template."""
    payload_json = json.dumps(payload, ensure_ascii=False)
    return _HTML_TEMPLATE.replace("__STATS_DATA__", payload_json)


# ---------------------------------------------------------------------------
# Panel class
# ---------------------------------------------------------------------------


class StatsChartPanel:
    """Floating NSPanel with WKWebView showing interactive usage statistics charts."""

    _WIDTH = 920
    _HEIGHT = 720

    def __init__(self) -> None:
        self._panel = None
        self._webview = None
        self._close_delegate = None

    def show(self, usage_stats: UsageStats) -> None:
        """Show the stats chart panel with current data."""
        from AppKit import NSApp

        NSApp.setActivationPolicy_(0)  # Regular (foreground)

        if self._panel is None:
            self._build_panel()

        # Inject fresh data every time show() is called
        payload = build_stats_payload(usage_stats)
        html = build_html(payload)

        from Foundation import NSURL

        self._webview.loadHTMLString_baseURL_(
            html, NSURL.URLWithString_("about:blank")
        )

        self._panel.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

    def close(self) -> None:
        """Close panel and restore accessory mode."""
        if self._panel is not None:
            from AppKit import NSApp

            self._panel.orderOut_(None)
            NSApp.setActivationPolicy_(1)  # Accessory (statusbar-only)

    def _build_panel(self) -> None:
        """Build NSPanel + WKWebView."""
        from AppKit import (
            NSBackingStoreBuffered,
            NSClosableWindowMask,
            NSMiniaturizableWindowMask,
            NSPanel,
            NSResizableWindowMask,
            NSStatusWindowLevel,
            NSTitledWindowMask,
        )
        from Foundation import NSMakeRect
        from WebKit import WKWebView

        style = (
            NSTitledWindowMask
            | NSClosableWindowMask
            | NSResizableWindowMask
            | NSMiniaturizableWindowMask
        )
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, self._WIDTH, self._HEIGHT),
            style,
            NSBackingStoreBuffered,
            False,
        )
        panel.setTitle_("Usage Statistics")
        panel.setLevel_(NSStatusWindowLevel)
        panel.setFloatingPanel_(True)
        panel.setHidesOnDeactivate_(False)
        panel.center()

        # Close delegate
        delegate_cls = _get_panel_close_delegate_class()
        delegate = delegate_cls.alloc().init()
        delegate._panel_ref = self
        panel.setDelegate_(delegate)
        self._close_delegate = delegate

        # WKWebView fills content area
        webview = WKWebView.alloc().initWithFrame_(
            NSMakeRect(0, 0, self._WIDTH, self._HEIGHT)
        )
        webview.setAutoresizingMask_(0x12)  # Width + Height sizable
        panel.contentView().addSubview_(webview)

        self._panel = panel
        self._webview = webview
