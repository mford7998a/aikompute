/**
 * AI Inference Gateway — Dashboard JavaScript
 */

const API_BASE = window.location.hostname === 'localhost' 
    ? 'http://localhost:4000' 
    : `${window.location.protocol}//${window.location.host}`;

let jwtToken = localStorage.getItem('jwt_token');
let currentUser = null;

// ============================================
// Init
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('api-base-url').textContent = API_BASE;
    document.getElementById('docs-base-url').textContent = API_BASE;
    document.querySelectorAll('.docs-url-placeholder').forEach(el => {
        el.textContent = API_BASE;
    });

    if (jwtToken) {
        showDashboard();
    }

    // Enter key handlers
    document.getElementById('login-password')?.addEventListener('keydown', e => {
        if (e.key === 'Enter') login();
    });
    document.getElementById('reg-name')?.addEventListener('keydown', e => {
        if (e.key === 'Enter') register();
    });
});

// ============================================
// Auth
// ============================================
function showLogin() {
    document.getElementById('login-form').style.display = 'block';
    document.getElementById('register-form').style.display = 'none';
    document.getElementById('api-key-reveal').style.display = 'none';
    hideError();
}

function showRegister() {
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('register-form').style.display = 'block';
    document.getElementById('api-key-reveal').style.display = 'none';
    hideError();
}

async function login() {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    if (!email || !password) return showError('Please fill in all fields');

    try {
        const res = await api('/api/auth/login', 'POST', { email, password });
        jwtToken = res.jwt_token;
        localStorage.setItem('jwt_token', jwtToken);
        currentUser = res;
        showDashboard();
    } catch (e) {
        showError(e.message);
    }
}

async function register() {
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-password').value;
    const display_name = document.getElementById('reg-name').value;
    if (!email || !password) return showError('Please fill in email and password');

    try {
        const res = await api('/api/auth/register', 'POST', { email, password, display_name });
        jwtToken = res.jwt_token;
        localStorage.setItem('jwt_token', jwtToken);
        currentUser = res;

        // Show API key
        document.getElementById('login-form').style.display = 'none';
        document.getElementById('register-form').style.display = 'none';
        document.getElementById('api-key-reveal').style.display = 'block';
        document.getElementById('new-api-key').textContent = res.api_key;
    } catch (e) {
        showError(e.message);
    }
}

function proceedToDashboard() {
    showDashboard();
}

function logout() {
    jwtToken = null;
    localStorage.removeItem('jwt_token');
    document.getElementById('dashboard').style.display = 'none';
    document.getElementById('auth-screen').style.display = 'flex';
    showLogin();
}

function copyKey() {
    const key = document.getElementById('new-api-key').textContent;
    navigator.clipboard.writeText(key);
    alert('API key copied!');
}

function showError(msg) {
    const el = document.getElementById('auth-error');
    el.textContent = msg;
    el.style.display = 'block';
}
function hideError() {
    document.getElementById('auth-error').style.display = 'none';
}

// ============================================
// Dashboard
// ============================================
async function showDashboard() {
    document.getElementById('auth-screen').style.display = 'none';
    document.getElementById('dashboard').style.display = 'flex';

    await loadBalance();
    await loadUsage();
    await loadKeys();
    await loadPackages();
    await loadTransactions();
}

function showTab(tab) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
}

// ============================================
// Balance
// ============================================
async function loadBalance() {
    try {
        const data = await api('/api/user/balance');
        document.getElementById('user-email').textContent = data.email;
        document.getElementById('balance-display').textContent = data.credits_display;
        document.getElementById('stat-balance').textContent = data.credits_display;
    } catch (e) {
        console.error('Failed to load balance:', e);
    }
}

// ============================================
// Usage
// ============================================
async function loadUsage() {
    try {
        const data = await api('/api/user/usage?days=30');

        // Stats
        let totalRequests = 0, totalTokens = 0;
        data.summary.forEach(s => {
            totalRequests += Number(s.request_count || 0);
            totalTokens += Number(s.total_tokens || 0);
        });
        document.getElementById('stat-requests').textContent = totalRequests.toLocaleString();
        document.getElementById('stat-tokens').textContent = formatTokens(totalTokens);

        // Summary table
        if (data.summary.length > 0) {
            let html = '<table class="data-table"><thead><tr><th>Model</th><th>Provider</th><th>Requests</th><th>Tokens</th><th>Credits</th><th>Avg Latency</th></tr></thead><tbody>';
            data.summary.forEach(s => {
                html += `<tr>
                    <td>${s.model}</td>
                    <td>${s.provider}</td>
                    <td>${Number(s.request_count).toLocaleString()}</td>
                    <td>${formatTokens(Number(s.total_tokens))}</td>
                    <td>${(Number(s.total_credits) / 1_000_000).toFixed(2)}</td>
                    <td>${s.avg_latency_ms}ms</td>
                </tr>`;
            });
            html += '</tbody></table>';
            document.getElementById('usage-summary').innerHTML = html;
        } else {
            document.getElementById('usage-summary').innerHTML = '<div class="card"><p style="color:var(--text-dim)">No usage data yet. Make your first API call!</p></div>';
        }

        // Daily table
        if (data.daily.length > 0) {
            let html = '<table class="data-table"><thead><tr><th>Date</th><th>Requests</th><th>Tokens</th><th>Credits</th></tr></thead><tbody>';
            data.daily.forEach(d => {
                html += `<tr>
                    <td>${d.date}</td>
                    <td>${Number(d.requests).toLocaleString()}</td>
                    <td>${formatTokens(Number(d.tokens))}</td>
                    <td>${(Number(d.credits) / 1_000_000).toFixed(2)}</td>
                </tr>`;
            });
            html += '</tbody></table>';
            document.getElementById('usage-daily').innerHTML = html;
        } else {
            document.getElementById('usage-daily').innerHTML = '';
        }
    } catch (e) {
        console.error('Failed to load usage:', e);
    }
}

// ============================================
// API Keys
// ============================================
async function loadKeys() {
    try {
        const data = await api('/api/user/keys');
        let html = '';
        data.keys.forEach(key => {
            html += `<div class="key-card">
                <div class="key-info">
                    <h3>${escapeHtml(key.name)}</h3>
                    <div class="key-meta">
                        <span class="key-prefix">${key.key_prefix}••••••••</span>
                        · ${key.is_active ? '🟢 Active' : '🔴 Revoked'}
                        ${key.last_used_at ? `· Last used: ${new Date(key.last_used_at).toLocaleDateString()}` : ''}
                    </div>
                </div>
                <div class="key-actions">
                    ${key.is_active ? `<button onclick="revokeKey('${key.id}')" class="btn btn-sm btn-danger">Revoke</button>` : ''}
                </div>
            </div>`;
        });
        document.getElementById('keys-list').innerHTML = html || '<div class="card"><p style="color:var(--text-dim)">No API keys yet.</p></div>';
    } catch (e) {
        console.error('Failed to load keys:', e);
    }
}

async function createKey() {
    const name = prompt('Key name:', 'New Key');
    if (!name) return;
    try {
        const data = await api('/api/user/keys', 'POST', { name });
        alert(`New API key created!\n\n${data.api_key}\n\nSave this key — it won't be shown again.`);
        navigator.clipboard.writeText(data.api_key);
        await loadKeys();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function revokeKey(keyId) {
    if (!confirm('Revoke this API key? This cannot be undone.')) return;
    try {
        await api(`/api/user/keys/${keyId}`, 'DELETE');
        await loadKeys();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

// ============================================
// Billing
// ============================================
async function loadPackages() {
    try {
        const data = await api('/api/billing/packages');
        let html = '';
        data.packages.forEach(pkg => {
            html += `<div class="package-card">
                <div class="package-name">${escapeHtml(pkg.name)}</div>
                <div class="package-credits">${pkg.credits_display} <span>credits</span></div>
                <div class="package-price">${pkg.price_usd}</div>
                <button onclick="purchasePackage('${pkg.id}')" class="btn btn-primary btn-full">Purchase</button>
            </div>`;
        });
        document.getElementById('packages-grid').innerHTML = html;
    } catch (e) {
        console.error('Failed to load packages:', e);
    }
}

async function purchasePackage(packageId) {
    if (!confirm('Purchase this credit package?')) return;
    try {
        const data = await api(`/api/billing/purchase/${packageId}`, 'POST');
        alert(data.message + `\nNew balance: ${data.new_balance_display} credits`);
        await loadBalance();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function loadTransactions() {
    try {
        const data = await api('/api/user/transactions?limit=20');
        let html = '';
        data.transactions.forEach(tx => {
            const isPositive = tx.amount > 0;
            html += `<div class="tx-item">
                <div>
                    <div class="tx-desc">${escapeHtml(tx.description || tx.transaction_type)}</div>
                    <div class="tx-date">${new Date(tx.created_at).toLocaleString()}</div>
                </div>
                <div class="tx-amount ${isPositive ? 'positive' : 'negative'}">
                    ${isPositive ? '+' : ''}${(tx.amount / 1_000_000).toFixed(4)} credits
                </div>
            </div>`;
        });
        document.getElementById('transactions-list').innerHTML = html || '<p style="color:var(--text-dim)">No transactions yet.</p>';
    } catch (e) {
        console.error('Failed to load transactions:', e);
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

    const res = await fetch(`${API_BASE}${path}`, opts);
    const data = await res.json();

    if (!res.ok) {
        if (res.status === 401) {
            logout();
            throw new Error('Session expired. Please sign in again.');
        }
        throw new Error(data.detail || data.message || 'Request failed');
    }
    return data;
}

function formatTokens(n) {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
    return n.toString();
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
