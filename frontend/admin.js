const STORAGE_KEY = 'tkv_admin_token';

const state = {
    token: null,
    engineer: null,
    sessions: [],
    loading: false,
};

const dom = {
    loginPanel: document.getElementById('login-panel'),
    loginForm: document.getElementById('login-form'),
    loginError: document.getElementById('login-error'),
    loginSubmit: document.getElementById('login-submit'),
    dashboardPanel: document.getElementById('dashboard-panel'),
    currentUser: document.getElementById('current-user'),
    logoutBtn: document.getElementById('logout-btn'),
    refreshBtn: document.getElementById('refresh-btn'),
    dashboardStatus: document.getElementById('dashboard-status'),
    sessionsWrapper: document.getElementById('sessions-wrapper'),
    sessionsTableBody: document.querySelector('#sessions-table tbody'),
    sessionsEmpty: document.getElementById('sessions-empty'),
};

init();

function init() {
    dom.loginForm.addEventListener('submit', handleLogin);
    dom.logoutBtn.addEventListener('click', handleLogout);
    dom.refreshBtn.addEventListener('click', loadSessions);

    const savedToken = localStorage.getItem(STORAGE_KEY);
    if (savedToken) {
        state.token = savedToken;
        verifySession().catch(() => switchToLogin());
    } else {
        switchToLogin();
    }
}

async function handleLogin(event) {
    event.preventDefault();
    hideElement(dom.loginError);

    const formData = new FormData(dom.loginForm);
    const username = formData.get('username')?.trim();
    const password = formData.get('password')?.trim();
    if (!username || !password) {
        showError('Укажите логин и пароль');
        return;
    }

    dom.loginSubmit.disabled = true;
    try {
        const data = await apiRequest('/api/auth/login', {
            method: 'POST',
            body: { username, password },
            auth: false,
        });
        state.token = data.access_token;
        localStorage.setItem(STORAGE_KEY, state.token);
        await verifySession();
        dom.loginForm.reset();
    } catch (error) {
        showError(error.message || 'Не удалось выполнить вход');
    } finally {
        dom.loginSubmit.disabled = false;
    }
}

async function handleLogout() {
    if (!state.token) {
        switchToLogin();
        return;
    }
    try {
        await apiRequest('/api/auth/logout', { method: 'POST' });
    } catch (_) {
        // Игнорируем ошибки при выходе
    }
    localStorage.removeItem(STORAGE_KEY);
    state.token = null;
    state.engineer = null;
    state.sessions = [];
    switchToLogin();
}

async function verifySession() {
    const profile = await apiRequest('/api/auth/me');
    state.engineer = profile;
    dom.currentUser.textContent = `${profile.username} · ${profile.role}`;
    switchToDashboard();
    await loadSessions();
}

async function loadSessions() {
    if (state.loading) {
        return;
    }
    state.loading = true;
    dom.refreshBtn.disabled = true;
    setStatus('Загрузка списка сессий...', 'info');
    try {
        const data = await apiRequest('/api/admin/sessions');
        state.sessions = data.sessions || [];
        renderSessions();
        if (!state.sessions.length) {
            setStatus('Новых сессий пока нет.', 'info');
        } else {
            hideElement(dom.dashboardStatus);
        }
    } catch (error) {
        setStatus(error.message || 'Не удалось обновить список.', 'error');
    } finally {
        dom.refreshBtn.disabled = false;
        state.loading = false;
    }
}

function renderSessions() {
    dom.sessionsTableBody.innerHTML = '';
    if (!state.sessions.length) {
        dom.sessionsWrapper.hidden = true;
        dom.sessionsEmpty.hidden = false;
        return;
    }
    dom.sessionsEmpty.hidden = true;
    dom.sessionsWrapper.hidden = false;

    state.sessions.forEach((session) => {
        const latest = session.analyses?.length ? session.analyses[session.analyses.length - 1] : null;
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="mono">${session.session_id}</td>
            <td>${formatDate(session.created_at)}</td>
            <td>${formatMode(session.mode)}</td>
            <td>${renderStatus(session.status)}</td>
            <td>${latest ? formatDate(latest.created_at) : '—'}</td>
            <td>${latest ? `${Math.round(latest.match_ratio * 100)}%` : '—'}</td>
            <td>${latest ? `${latest.missing_tool_ids.length} / ${latest.unexpected_labels.length}` : '—'}</td>
        `;
        dom.sessionsTableBody.appendChild(row);
    });
}

function switchToLogin() {
    dom.loginPanel.hidden = false;
    dom.dashboardPanel.hidden = true;
    hideElement(dom.loginError);
    hideElement(dom.dashboardStatus);
    dom.sessionsEmpty.hidden = true;
    dom.sessionsWrapper.hidden = true;
}

function switchToDashboard() {
    dom.loginPanel.hidden = true;
    dom.dashboardPanel.hidden = false;
}

function showError(message) {
    dom.loginError.textContent = message;
    dom.loginError.hidden = false;
}

function hideElement(element) {
    if (element) {
        element.hidden = true;
    }
}

function setStatus(message, tone = 'info') {
    if (!dom.dashboardStatus) {
        return;
    }
    dom.dashboardStatus.textContent = message;
    dom.dashboardStatus.classList.toggle('notice--error', tone === 'error');
    dom.dashboardStatus.classList.toggle('notice--info', tone !== 'error');
    dom.dashboardStatus.hidden = false;
}

function formatDate(value) {
    if (!value) {
        return '—';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function formatMode(mode) {
    if (mode === 'handout') {
        return 'Выдача';
    }
    if (mode === 'handover') {
        return 'Возврат';
    }
    return mode;
}

function renderStatus(status) {
    if (status === 'completed') {
        return '<span class="badge badge--success">Завершена</span>';
    }
    return '<span class="badge badge--pending">В работе</span>';
}

async function apiRequest(path, options = {}) {
    const { method = 'GET', body = null, auth = true } = options;
    const headers = {};
    if (auth) {
        if (!state.token) {
            throw new Error('Необходимо войти в систему');
        }
        headers.Authorization = `Bearer ${state.token}`;
    }
    if (body) {
        headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(path, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
    });

    if (response.status === 401) {
        localStorage.removeItem(STORAGE_KEY);
        state.token = null;
        state.engineer = null;
        switchToLogin();
        throw new Error('Сессия истекла, войдите снова');
    }

    if (!response.ok) {
        let detail = 'Неизвестная ошибка';
        try {
            const payload = await response.json();
            detail = payload.detail || detail;
        } catch (_) {
            // пусто
        }
        throw new Error(detail);
    }

    if (response.status === 204) {
        return null;
    }
    return response.json();
}
