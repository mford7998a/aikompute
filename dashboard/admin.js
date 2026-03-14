/**
 * AI Inference Gateway — Admin Dashboard JavaScript
 */

const API_BASE = window.location.hostname === 'localhost'
    ? 'http://localhost:4000'
    : `${window.location.protocol}//${window.location.hostname}/v1`;

let jwtToken = localStorage.getItem('admin_token');
let adminUser = null;
let charts = {};

// ============================================
// Init
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    if (jwtToken) {
        showDashboard();
    }

    // Enter key handlers
    document.getElementById('login-password')?.addEventListener('keydown', e => {
        if (e.key === 'Enter') adminLogin();
    });
});

// ============================================
// Auth
// ============================================
async function adminLogin() {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    if (!email || !password) return showError('Please fill in all fields');

    try {
        const res = await api('/api/auth/login', 'POST', { email, password });
        if (!res.is_admin) {
            throw new Error('Access Denied: Admin privileges required.');
        }
        jwtToken = res.jwt_token;
        localStorage.setItem('admin_token', jwtToken);
        adminUser = res;
        showDashboard();
    } catch (e) {
        showError(e.message);
    }
}

function logout() {
    jwtToken = null;
    localStorage.removeItem('admin_token');
    document.getElementById('dashboard').style.display = 'none';
    document.getElementById('auth-screen').style.display = 'flex';
}

function showError(msg) {
    const el = document.getElementById('auth-error');
    el.textContent = msg;
    el.style.display = 'block';
}

// ============================================
// Dashboard Control
// ============================================
async function showDashboard() {
    document.getElementById('auth-screen').style.display = 'none';
    document.getElementById('dashboard').style.display = 'flex';
    document.getElementById('admin-email').textContent = adminUser?.email || 'Admin';

    await loadOverview();
    await loadTrends();
    await loadUsers();
    await loadForecast();
    await loadProviders();
    await loadModels();
}

function showTab(tab) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
}

// ============================================
// Data Loading
// ============================================

async function loadOverview() {
    try {
        const data = await api('/api/admin/dashboard');

        // Summary stats
        document.getElementById('total-revenue').textContent = data.financials.total_revenue_display;
        document.getElementById('stat-total-users').textContent = data.users.total_users;
        document.getElementById('stat-total-tokens').textContent = formatTokens(data.tokens.tokens_30d);
        document.getElementById('stat-revenue-30d').textContent = data.financials.revenue_30d_display;
        document.getElementById('stat-error-rate').textContent = data.health.error_rate + '%';

        // Financial tab stats
        document.getElementById('fin-all-time').textContent = data.financials.total_revenue_display;
        document.getElementById('fin-arpu').textContent = '$' + data.financials.arpu;
        document.getElementById('fin-purchases').textContent = data.financials.total_purchases;

        // Provider summary list
        let html = '';
        data.providers.forEach(p => {
            let statusClass = p.error_rate < 5 ? 'status-healthy' : (p.error_rate < 20 ? 'status-degraded' : 'status-unhealthy');
            html += `
                <div class="account-need-item">
                    <div>
                        <span class="provider-pill ${statusClass}">${p.provider_type}</span>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-weight: 600;">${formatTokens(p.total_tokens)}</div>
                        <div style="font-size: 0.75rem; color: var(--text-dim);">${p.error_rate}% error</div>
                    </div>
                </div>
            `;
        });
        document.getElementById('provider-summary-list').innerHTML = html || '<p>No data</p>';

    } catch (e) {
        console.error('Failed to load overview:', e);
    }
}

async function loadTrends() {
    try {
        const data = await api('/api/admin/trends?days=30');

        // Usage Chart (Tokens)
        renderChart('usageChart', {
            type: 'line',
            data: {
                labels: data.usage.map(d => d.date),
                datasets: [
                    {
                        label: 'Total Tokens',
                        data: data.usage.map(d => d.tokens),
                        borderColor: '#6366f1',
                        backgroundColor: 'rgba(99, 102, 241, 0.1)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: 'Requests',
                        data: data.usage.map(d => d.requests),
                        borderColor: '#10b981',
                        tension: 0.4,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y1: { position: 'right', beginAtZero: true, grid: { display: false } },
                    x: { grid: { color: 'rgba(255,255,255,0.05)' } }
                }
            }
        });

        // Revenue Chart
        renderChart('revenueChart', {
            type: 'bar',
            data: {
                labels: data.revenue.map(d => d.date),
                datasets: [{
                    label: 'Daily Revenue ($)',
                    data: data.revenue.map(d => d.revenue / 1_000_000),
                    backgroundColor: '#10b981'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                    x: { grid: { color: 'rgba(255,255,255,0.05)' } }
                }
            }
        });

    } catch (e) {
        console.error('Failed to load trends:', e);
    }
}

async function loadForecast() {
    try {
        const data = await api('/api/admin/forecast');
        if (data.message) {
            document.getElementById('forecast-growth').textContent = 'Calculating...';
            return;
        }

        document.getElementById('forecast-growth').textContent = (data.historical_summary.growth_rate_pct > 0 ? '+' : '') + data.historical_summary.growth_rate_pct + '%';
        document.getElementById('target-daily-tokens').textContent = formatTokens(data.prediction_30d.predicted_daily_tokens);
        document.getElementById('target-monthly-tokens').textContent = formatTokens(data.prediction_30d.predicted_monthly_tokens);
        document.getElementById('accounts-to-acquire').textContent = data.prediction_30d.total_accounts_needed;
        document.getElementById('predicted-users').textContent = data.prediction_30d.predicted_active_users;

        // Forecast Chart
        renderChart('forecastChart', {
            type: 'line',
            data: {
                labels: data.forecast.map(d => d.date),
                datasets: [{
                    label: 'Predicted Daily Tokens',
                    data: data.forecast.map(d => d.predicted_tokens),
                    borderColor: '#f59e0b',
                    borderDash: [5, 5],
                    backgroundColor: 'rgba(245, 158, 11, 0.05)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                    x: { grid: { color: 'rgba(255,255,255,0.05)' } }
                }
            }
        });

        // Account Needs
        let html = '<div class="account-need-list">';
        for (const [provider, stats] of Object.entries(data.account_needs)) {
            html += `
                <div class="account-need-item">
                    <div>
                        <div style="font-weight: 600;">${provider}</div>
                        <div style="font-size: 0.75rem; color: var(--text-dim);">${stats.traffic_share_pct}% of traffic</div>
                    </div>
                    <div style="text-align: right;">
                        <div>Need: <span class="need-count">${stats.accounts_needed_30d}</span></div>
                        <div style="font-size: 0.75rem; color: var(--text-dim);">Current: ${stats.accounts_needed_now}</div>
                    </div>
                </div>
            `;
        }
        html += '</div>';
        document.getElementById('account-needs-container').innerHTML = html;

    } catch (e) {
        console.error('Failed to load forecast:', e);
    }
}

async function loadUsers() {
    const search = document.getElementById('user-search').value;
    try {
        const data = await api(`/api/admin/users?search=${encodeURIComponent(search)}`);
        let html = '';
        data.users.forEach(u => {
            html += `
                <tr>
                    <td>
                        <div style="font-weight: 600;">${escapeHtml(u.display_name || 'No Name')}</div>
                        <div style="font-size: 0.75rem; color: var(--text-dim);">${u.email}</div>
                    </td>
                    <td>${u.credit_balance_display}</td>
                    <td>${formatTokens(u.total_tokens)}</td>
                    <td>${u.requests_today}</td>
                    <td>${u.last_active ? new Date(u.last_active).toLocaleDateString() : 'Never'}</td>
                    <td>${u.is_active ? '<span class="status-healthy">Active</span>' : '<span class="status-unhealthy">Suspended</span>'}</td>
                    <td>
                        <button onclick="adjustCredits('${u.id}')" class="btn btn-sm btn-ghost">Add $</button>
                        <button onclick="toggleUser('${u.id}')" class="btn btn-sm btn-ghost">${u.is_active ? 'Suspend' : 'Unsuspend'}</button>
                    </td>
                </tr>
            `;
        });
        document.getElementById('users-table-body').innerHTML = html || '<tr><td colspan="7">No users found.</td></tr>';
    } catch (e) {
        console.error('Failed to load users:', e);
    }
}

async function adjustCredits(userId) {
    const amount = prompt('Amount to add in credits (e.g. 5.00):', '10.0');
    if (!amount) return;
    const microCredits = Math.round(parseFloat(amount) * 1_000_000);
    try {
        await api(`/api/admin/users/${userId}/credits?amount=${microCredits}`, 'POST');
        alert('Credits updated!');
        await loadUsers();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function toggleUser(userId) {
    if (!confirm('Change user status?')) return;
    try {
        await api(`/api/admin/users/${userId}/toggle`, 'POST');
        await loadUsers();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function loadProviders() {
    try {
        const data = await api('/api/admin/providers');

        let html = '';
        data.providers.forEach(p => {
            let statusClass = `status-${p.health}`;
            html += `
                <div class="user-mini-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                        <span class="provider-pill ${statusClass}">${p.provider_type}</span>
                        <span style="font-size: 0.75rem; color: var(--text-dim);">Last: ${new Date(p.last_request).toLocaleTimeString()}</span>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                        <div>
                            <div style="font-size: 0.75rem; color: var(--text-dim);">Req (24h)</div>
                            <div style="font-weight: 700;">${p.requests_24h.toLocaleString()}</div>
                        </div>
                        <div>
                            <div style="font-size: 0.75rem; color: var(--text-dim);">Tokens</div>
                            <div style="font-weight: 700;">${formatTokens(p.tokens_24h)}</div>
                        </div>
                        <div>
                            <div style="font-size: 0.75rem; color: var(--text-dim);">Latency</div>
                            <div style="font-weight: 700;">${p.avg_latency}ms</div>
                        </div>
                        <div>
                            <div style="font-size: 0.75rem; color: var(--text-dim);">Error Rate</div>
                            <div style="font-weight: 700; color: ${p.error_rate > 5 ? '#ef4444' : 'inherit'};">${p.error_rate}%</div>
                        </div>
                    </div>
                </div>
            `;
        });
        document.getElementById('provider-health-grid').innerHTML = html;

        // Provider Pie Chart
        renderChart('providerChart', {
            type: 'doughnut',
            data: {
                labels: data.providers.map(p => p.provider_type),
                datasets: [{
                    data: data.providers.map(p => p.tokens_24h),
                    backgroundColor: [
                        '#6366f1', '#10b981', '#f59e0b', '#ef4444', '#a855f7', '#ec4899'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { color: '#94a3b8' } }
                }
            }
        });

    } catch (e) {
        console.error('Failed to load providers:', e);
    }
}

async function loadModels() {
    try {
        const data = await api('/api/admin/models');
        let html = '';
        data.models.forEach(m => {
            html += `
                <tr>
                    <td><code>${m.model}</code></td>
                    <td><span class="provider-pill status-healthy">${m.provider_type}</span></td>
                    <td>${m.requests.toLocaleString()}</td>
                    <td>${formatTokens(m.tokens)}</td>
                    <td>${m.avg_latency}ms</td>
                    <td>${m.unique_users}</td>
                    <td style="color: #10b981;">+$${(m.credits / 1_000_000).toFixed(2)}</td>
                </tr>
            `;
        });
        document.getElementById('models-table-body').innerHTML = html;
    } catch (e) {
        console.error('Failed to load models:', e);
    }
}

// ============================================
// Helpers
// ============================================

async function api(path, method = 'GET', body = null) {
    const headers = { 'Content-Type': 'application/json' };
    if (jwtToken) headers['Authorization'] = `Bearer ${jwtToken}`;

    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    const res = await fetch(`${path.startsWith('http') ? '' : API_BASE}${path}`, opts);
    const data = await res.json();

    if (!res.ok) {
        throw new Error(data.detail || data.message || 'Request failed');
    }
    return data;
}

function renderChart(id, config) {
    if (charts[id]) charts[id].destroy();
    const ctx = document.getElementById(id).getContext('2d');
    charts[id] = new Chart(ctx, config);
}

function formatTokens(n) {
    if (!n) return '0';
    if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + 'B';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
    return n.toString();
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
