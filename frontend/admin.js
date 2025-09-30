const STORAGE_KEY = 'tkv_admin_token';

const state = {
    token: null,
    engineer: null,
    sessions: [],
    loading: false,
    engineers: [],
    usersLoading: false,
    dashboard: null,
    metricsLoading: false,
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
    metricsStatus: document.getElementById('metrics-status'),
    metricsGrid: document.getElementById('metrics-grid'),
    metricTotalSessions: document.getElementById('metric-total-sessions'),
    metricPendingSessions: document.getElementById('metric-pending-sessions'),
    metricCompletedSessions: document.getElementById('metric-completed-sessions'),
    metricTotalEngineers: document.getElementById('metric-total-engineers'),
    metricTotalAnalyses: document.getElementById('metric-total-analyses'),
    modeBreakdown: document.getElementById('mode-breakdown'),
    latestSessions: document.getElementById('latest-sessions'),
    latestSessionsList: document.getElementById('latest-sessions-list'),
    sessionsWrapper: document.getElementById('sessions-wrapper'),
    sessionsTableBody: document.querySelector('#sessions-table tbody'),
    sessionsEmpty: document.getElementById('sessions-empty'),
    usersDivider: document.getElementById('users-divider'),
    usersPanel: document.getElementById('users-panel'),
    usersEmpty: document.getElementById('users-empty'),
    usersTable: document.getElementById('users-table'),
    usersTableBody: document.querySelector('#users-table tbody'),
    reloadUsers: document.getElementById('reload-users'),
    createUserForm: document.getElementById('create-user-form'),
    createUserSubmit: document.getElementById('create-user-submit'),
    userFormError: document.getElementById('user-form-error'),
    userFormSuccess: document.getElementById('user-form-success'),
};

init();

function init() {
    dom.loginForm.addEventListener('submit', handleLogin);
    dom.logoutBtn.addEventListener('click', handleLogout);
    dom.refreshBtn.addEventListener('click', handleRefresh);
    dom.reloadUsers?.addEventListener('click', loadEngineers);
    dom.createUserForm?.addEventListener('submit', handleCreateEngineer);

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
    await loadDashboard();
    await loadSessions();
    await loadEngineers();
}

async function loadSessions(options = {}) {
    const { manageButton = true } = options;
    if (state.loading) {
        return;
    }
    state.loading = true;
    if (manageButton && dom.refreshBtn) {
        dom.refreshBtn.disabled = true;
    }
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
        if (manageButton && dom.refreshBtn) {
            dom.refreshBtn.disabled = false;
        }
        state.loading = false;
    }
}

async function handleRefresh() {
    if (dom.refreshBtn) {
        dom.refreshBtn.disabled = true;
    }
    try {
        await loadDashboard();
        await loadSessions({ manageButton: false });
    } finally {
        if (dom.refreshBtn) {
            dom.refreshBtn.disabled = false;
        }
    }
}

async function loadDashboard() {
    if (!dom.metricsGrid) {
        return;
    }
    if (!state.engineer || state.engineer.role !== 'admin') {
        toggleDashboard(false);
        setMetricsStatus(null);
        return;
    }
    if (state.metricsLoading) {
        return;
    }
    state.metricsLoading = true;
    setMetricsStatus('Обновление метрик...', 'info');
    try {
        const data = await apiRequest('/api/admin/dashboard');
        state.dashboard = data;
        renderDashboard();
        setMetricsStatus(null);
    } catch (error) {
        setMetricsStatus(error.message || 'Не удалось обновить метрики', 'error');
    } finally {
        state.metricsLoading = false;
    }
}

function renderDashboard() {
    if (!state.dashboard || !dom.metricsGrid) {
        toggleDashboard(false);
        return;
    }
    const metrics = state.dashboard;
    dom.metricsGrid.hidden = false;

    if (dom.metricTotalSessions) {
        dom.metricTotalSessions.textContent = metrics.total_sessions;
    }
    if (dom.metricPendingSessions) {
        dom.metricPendingSessions.textContent = metrics.pending_sessions;
    }
    if (dom.metricCompletedSessions) {
        dom.metricCompletedSessions.textContent = metrics.completed_sessions;
    }
    if (dom.metricTotalEngineers) {
        dom.metricTotalEngineers.textContent = metrics.total_engineers;
    }
    if (dom.metricTotalAnalyses) {
        dom.metricTotalAnalyses.textContent = metrics.total_analyses;
    }

    renderModeBreakdown(metrics.sessions_by_mode || []);
    renderLatestSessions(metrics.latest_sessions || []);
}

function renderModeBreakdown(items) {
    if (!dom.modeBreakdown) {
        return;
    }
    dom.modeBreakdown.innerHTML = '';
    if (!items.length) {
        dom.modeBreakdown.hidden = true;
        return;
    }
    items.forEach((item) => {
        const chip = document.createElement('div');
        chip.className = 'mode-chip';
        chip.innerHTML = `
            <span class="mode-chip__label">${formatMode(item.mode)}</span>
            <span class="mode-chip__value">${item.count}</span>
        `;
        dom.modeBreakdown.appendChild(chip);
    });
    dom.modeBreakdown.hidden = false;
}

function renderLatestSessions(items) {
    if (!dom.latestSessions || !dom.latestSessionsList) {
        return;
    }
    dom.latestSessionsList.innerHTML = '';
    if (!items.length) {
        dom.latestSessions.hidden = true;
        return;
    }
    items.forEach((item) => {
        const li = document.createElement('li');
        li.className = 'latest-sessions__item';
        const owner = item.engineer_username
            ? `${item.engineer_username} (#${item.engineer_id})`
            : '—';
        li.innerHTML = `
            <span class="mono">${item.session_id}</span>
            <span>${formatDate(item.created_at)}</span>
            <span>${renderStatus(item.status)}</span>
            <span class="latest-sessions__owner">${owner}</span>
        `;
        dom.latestSessionsList.appendChild(li);
    });
    dom.latestSessions.hidden = false;
}

function toggleDashboard(visible) {
    if (dom.metricsGrid) {
        dom.metricsGrid.hidden = !visible;
    }
    if (dom.modeBreakdown) {
        dom.modeBreakdown.hidden = !visible;
        dom.modeBreakdown.innerHTML = '';
    }
    if (dom.latestSessions) {
        dom.latestSessions.hidden = !visible;
        if (dom.latestSessionsList) {
            dom.latestSessionsList.innerHTML = '';
        }
    }
    if (!visible) {
        state.dashboard = null;
        if (dom.metricsStatus) {
            dom.metricsStatus.hidden = true;
        }
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
        const owner = session.engineer ? `${session.engineer.username} (#${session.engineer.id})` : '—';
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="mono">${session.session_id}</td>
            <td>${owner}</td>
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

async function loadEngineers() {
    if (!dom.usersPanel) {
        return;
    }
    if (!state.engineer || state.engineer.role !== 'admin') {
        toggleUsersPanel(false);
        return;
    }
    if (state.usersLoading) {
        return;
    }
    state.usersLoading = true;
    if (dom.reloadUsers) {
        dom.reloadUsers.disabled = true;
    }
    try {
        toggleUsersPanel(true);
        const data = await apiRequest('/api/admin/engineers');
        state.engineers = data.engineers || [];
        renderEngineers();
    } catch (error) {
        if (dom.userFormError) {
            dom.userFormError.textContent = error.message || 'Не удалось получить список пользователей';
            dom.userFormError.hidden = false;
        }
    } finally {
        if (dom.reloadUsers) {
            dom.reloadUsers.disabled = false;
        }
        state.usersLoading = false;
    }
}

function renderEngineers() {
    if (!dom.usersTable || !dom.usersEmpty || !dom.usersTableBody) {
        return;
    }
    if (!state.engineers.length) {
        dom.usersEmpty.hidden = false;
        dom.usersTable.hidden = true;
        dom.usersTableBody.innerHTML = '';
        return;
    }
    dom.usersEmpty.hidden = true;
    dom.usersTable.hidden = false;
    dom.usersTableBody.innerHTML = '';
    state.engineers.forEach((engineer) => {
        const row = document.createElement('tr');
        const created = formatDate(engineer.created_at);
        row.innerHTML = `
            <td>${engineer.username}</td>
            <td><span class="badge ${engineer.role === 'admin' ? 'badge--admin' : 'badge--muted'}">${engineer.role}</span></td>
            <td>${created}</td>
        `;
        dom.usersTableBody.appendChild(row);
    });
}

function toggleUsersPanel(visible) {
    if (dom.usersDivider) {
        dom.usersDivider.hidden = !visible;
    }
    if (dom.usersPanel) {
        dom.usersPanel.hidden = !visible;
    }
}

async function handleCreateEngineer(event) {
    event.preventDefault();
    hideElement(dom.userFormError);
    hideElement(dom.userFormSuccess);

    if (!dom.createUserForm) {
        return;
    }

    if (!state.engineer || state.engineer.role !== 'admin') {
        if (dom.userFormError) {
            dom.userFormError.textContent = 'Недостаточно прав для создания пользователей';
            dom.userFormError.hidden = false;
        }
        return;
    }

    const formData = new FormData(dom.createUserForm);
    const username = formData.get('username')?.trim();
    const password = formData.get('password')?.trim();
    const role = formData.get('role');

    if (!username || !password) {
        if (dom.userFormError) {
            dom.userFormError.textContent = 'Заполните логин и пароль';
            dom.userFormError.hidden = false;
        }
        return;
    }

    if (dom.createUserSubmit) {
        dom.createUserSubmit.disabled = true;
    }
    try {
        await apiRequest('/api/admin/engineers', {
            method: 'POST',
            body: { username, password, role },
        });
        if (dom.userFormSuccess) {
            dom.userFormSuccess.hidden = false;
        }
        dom.createUserForm?.reset();
        await loadEngineers();
    } catch (error) {
        if (dom.userFormError) {
            dom.userFormError.textContent = error.message || 'Не удалось создать пользователя';
            dom.userFormError.hidden = false;
        }
    } finally {
        if (dom.createUserSubmit) {
            dom.createUserSubmit.disabled = false;
        }
    }
}

function switchToLogin() {
    dom.loginPanel.hidden = false;
    dom.dashboardPanel.hidden = true;
    hideElement(dom.loginError);
    hideElement(dom.dashboardStatus);
    dom.sessionsEmpty.hidden = true;
    dom.sessionsWrapper.hidden = true;
    toggleUsersPanel(false);
    toggleDashboard(false);
    hideElement(dom.userFormError);
    hideElement(dom.userFormSuccess);
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

function setMetricsStatus(message, tone = 'info') {
    if (!dom.metricsStatus) {
        return;
    }
    if (!message) {
        dom.metricsStatus.hidden = true;
        return;
    }
    dom.metricsStatus.textContent = message;
    dom.metricsStatus.classList.toggle('notice--error', tone === 'error');
    dom.metricsStatus.classList.toggle('notice--info', tone !== 'error');
    dom.metricsStatus.hidden = false;
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
