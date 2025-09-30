const STORAGE_KEY = 'tkv_console_token';

const state = {
    token: null,
    engineer: null,
    toolCatalog: [],
    toolIndex: {},
    sessionId: null,
    sessionMode: null,
    expectedToolIds: [],
    threshold: 0.9,
    latestAnalysis: null,
    currentStep: 1,
};

const dom = {
    loginPanel: document.getElementById('login-panel'),
    loginForm: document.getElementById('login-form'),
    loginError: document.getElementById('login-error'),
    loginSubmit: document.getElementById('login-submit'),
    wizardContainer: document.getElementById('wizard-container'),
    currentUser: document.getElementById('current-user'),
    logoutBtn: document.getElementById('logout-btn'),
    status: document.getElementById('system-status'),
    stepperItems: Array.from(document.querySelectorAll('[data-step-index]')),
    stepSections: Array.from(document.querySelectorAll('[data-step]')),
    toolList: document.getElementById('tool-list'),
    sessionForm: document.getElementById('session-form'),
    sessionFormStatus: document.getElementById('session-form-status'),
    thresholdSlider: document.getElementById('threshold'),
    thresholdValue: document.getElementById('threshold-value'),
    dropzone: document.getElementById('dropzone'),
    selectFileButton: document.getElementById('select-file'),
    fileInput: document.getElementById('file-input'),
    previewWrapper: document.getElementById('image-preview'),
    previewImg: document.getElementById('preview-img'),
    resetUploadButton: document.getElementById('reset-upload'),
    backToConfig: document.getElementById('back-to-config'),
    backToUpload: document.getElementById('back-to-upload'),
    startNewSession: document.getElementById('start-new-session'),
    sessionSummary: document.getElementById('session-summary'),
    sessionTools: document.getElementById('session-tools'),
    sessionId: document.getElementById('session-id'),
    sessionMode: document.getElementById('session-mode'),
    sessionThreshold: document.getElementById('session-threshold'),
    sessionExpected: document.getElementById('session-expected'),
    sessionSummaryResults: document.getElementById('session-summary-results'),
    sessionToolsResults: document.getElementById('session-tools-results'),
    sessionIdResults: document.getElementById('session-id-results'),
    sessionModeResults: document.getElementById('session-mode-results'),
    sessionThresholdResults: document.getElementById('session-threshold-results'),
    sessionExpectedResults: document.getElementById('session-expected-results'),
    analysisSummary: document.getElementById('analysis-summary'),
    analysisContent: document.getElementById('analysis-content'),
    detectedTableBody: document.querySelector('#detected-table tbody'),
    missingList: document.getElementById('missing-list'),
    unexpectedList: document.getElementById('unexpected-list'),
};

init();

function init() {
    setupThresholdSlider();
    attachFormHandlers();
    attachUploadHandlers();
    attachNavigationHandlers();
    attachAuthHandlers();
    switchToLogin();

    const savedToken = localStorage.getItem(STORAGE_KEY);
    if (savedToken) {
        state.token = savedToken;
        verifySession().catch((error) => {
            console.error(error);
        });
    }
}

function attachAuthHandlers() {
    dom.loginForm?.addEventListener('submit', handleLogin);
    dom.logoutBtn?.addEventListener('click', handleLogout);
}

async function handleLogin(event) {
    event.preventDefault();
    hideAuthError();

    const formData = new FormData(dom.loginForm);
    const username = formData.get('username')?.trim();
    const password = formData.get('password')?.trim();

    if (!username || !password) {
        showAuthError('Укажите логин и пароль');
        return;
    }

    if (dom.loginSubmit) {
        dom.loginSubmit.disabled = true;
    }

    try {
        const data = await apiRequest('/api/auth/login', {
            method: 'POST',
            body: { username, password },
            auth: false,
        });
        state.token = data.access_token;
        localStorage.setItem(STORAGE_KEY, state.token);
        await verifySession();
        dom.loginForm?.reset();
    } catch (error) {
        showAuthError(error.message || 'Не удалось выполнить вход');
    } finally {
        if (dom.loginSubmit) {
            dom.loginSubmit.disabled = false;
        }
    }
}

async function handleLogout() {
    if (state.token) {
        try {
            await fetch('/api/auth/logout', {
                method: 'POST',
                headers: { Authorization: `Bearer ${state.token}` },
            });
        } catch (_) {
            // ignore logout errors
        }
    }
    handleUnauthorized();
}

async function verifySession() {
    if (!state.token) {
        throw new Error('Требуется авторизация');
    }
    try {
        const profile = await apiRequest('/api/auth/me');
        state.engineer = profile;
        await fetchToolCatalog();
        resetWizard(true);
        switchToWizard();
    } catch (error) {
        handleUnauthorized(error.message);
        throw error;
    }
}

function switchToLogin() {
    if (dom.loginPanel) {
        dom.loginPanel.hidden = false;
    }
    if (dom.wizardContainer) {
        dom.wizardContainer.hidden = true;
    }
    if (dom.logoutBtn) {
        dom.logoutBtn.hidden = true;
    }
    if (dom.currentUser) {
        dom.currentUser.hidden = true;
        dom.currentUser.textContent = '';
    }
    hideAuthError();
    setStatus('Необходимо войти в систему');
}

function switchToWizard() {
    hideAuthError();
    if (dom.loginPanel) {
        dom.loginPanel.hidden = true;
    }
    if (dom.wizardContainer) {
        dom.wizardContainer.hidden = false;
    }
    if (dom.logoutBtn) {
        dom.logoutBtn.hidden = false;
    }
    if (dom.currentUser && state.engineer) {
        dom.currentUser.textContent = `${state.engineer.username} · ${state.engineer.role}`;
        dom.currentUser.hidden = false;
    }
    goToStep(state.sessionId ? state.currentStep : 1);
    setStatus(state.sessionId ? 'Сессия активна' : 'Готов к работе');
}

function showAuthError(message) {
    if (!dom.loginError) {
        return;
    }
    dom.loginError.textContent = message;
    dom.loginError.hidden = false;
}

function hideAuthError() {
    if (dom.loginError) {
        dom.loginError.hidden = true;
    }
}

function handleUnauthorized(message) {
    localStorage.removeItem(STORAGE_KEY);
    state.token = null;
    state.engineer = null;
    resetWizard(true);
    switchToLogin();
    if (message) {
        showAuthError(message);
    }
}

async function apiRequest(path, options = {}) {
    const { method = 'GET', body = null, auth = true, headers = {} } = options;
    const requestHeaders = { ...headers };

    if (auth) {
        if (!state.token) {
            throw new Error('Требуется авторизация');
        }
        requestHeaders.Authorization = `Bearer ${state.token}`;
    }

    let payload = body;
    if (body && !(body instanceof FormData) && typeof body !== 'string') {
        requestHeaders['Content-Type'] = 'application/json';
        payload = JSON.stringify(body);
    }

    const response = await fetch(path, {
        method,
        headers: requestHeaders,
        body: payload,
    });

    if (response.status === 401) {
        handleUnauthorized('Сессия истекла, войдите снова');
        throw new Error('Сессия истекла, войдите снова');
    }

    if (!response.ok) {
        let detail = 'Неизвестная ошибка';
        try {
            const payload = await response.json();
            detail = payload.detail || detail;
        } catch (_) {
            // ignore json parsing errors
        }
        throw new Error(detail);
    }

    if (response.status === 204) {
        return null;
    }

    const contentType = response.headers.get('Content-Type') || '';
    if (contentType.includes('application/json')) {
        return response.json();
    }
    return response.text();
}

function setupThresholdSlider() {
    if (!dom.thresholdSlider || !dom.thresholdValue) {
        return;
    }
    dom.thresholdSlider.addEventListener('input', () => {
        const value = Number(dom.thresholdSlider.value);
        dom.thresholdValue.textContent = `${value}%`;
    });
}

function attachFormHandlers() {
    if (!dom.sessionForm) {
        return;
    }
    dom.sessionForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!state.toolCatalog.length) {
            showFormStatus('Каталог инструментов ещё загружается, попробуйте позже.', 'error');
            return;
        }

        const formData = new FormData(dom.sessionForm);
        const mode = formData.get('mode');
        const thresholdPercent = Number(formData.get('threshold')) || 90;
        const threshold = Number((thresholdPercent / 100).toFixed(2));
        const expectedTools = Array.from(dom.sessionForm.querySelectorAll('input[name="expected"]:checked'))
            .map((input) => input.value);

        if (!expectedTools.length) {
            showFormStatus('Выберите хотя бы один инструмент из списка.', 'error');
            return;
        }

        if (!state.token) {
            showFormStatus('Авторизуйтесь, чтобы создать сессию.', 'error');
            setStatus('Необходимо войти в систему');
            return;
        }

        try {
            showFormStatus('Создание сессии...', 'info');
            setStatus('Создание сессии...');
            const payload = {
                mode,
                expected_tool_ids: expectedTools,
                threshold,
            };
            const session = await apiRequest('/api/sessions', {
                method: 'POST',
                body: payload,
            });
            applySession(session);
            showFormStatus('Сессия создана. Можно переходить к загрузке.', 'success');
            setStatus('Сессия активна');
        } catch (error) {
            console.error(error);
            showFormStatus(error.message || 'Не удалось создать сессию', 'error');
            if (state.token) {
                setStatus('Ошибка при создании сессии');
            }
        }
    });
}

function attachUploadHandlers() {
    if (!dom.dropzone || !dom.fileInput) {
        return;
    }
    dom.selectFileButton?.addEventListener('click', () => dom.fileInput.click());
    dom.fileInput.addEventListener('change', () => handleFileList(dom.fileInput.files));
    dom.resetUploadButton?.addEventListener('click', () => {
        resetUpload();
        goToStep(2);
    });

    ['dragenter', 'dragover'].forEach((eventName) => {
        dom.dropzone.addEventListener(eventName, (event) => {
            event.preventDefault();
            dom.dropzone.classList.add('dropzone--active');
        });
    });

    ['dragleave', 'drop'].forEach((eventName) => {
        dom.dropzone.addEventListener(eventName, (event) => {
            event.preventDefault();
            dom.dropzone.classList.remove('dropzone--active');
        });
    });

    dom.dropzone.addEventListener('drop', (event) => {
        const files = event.dataTransfer?.files;
        if (files?.length) {
            handleFileList(files);
        }
    });
}

function attachNavigationHandlers() {
    dom.backToConfig?.addEventListener('click', () => goToStep(1));
    dom.backToUpload?.addEventListener('click', () => {
        if (state.sessionId) {
            goToStep(2);
        }
    });
    dom.startNewSession?.addEventListener('click', () => {
        resetWizard();
        goToStep(1);
    });
}

async function fetchToolCatalog() {
    if (!dom.toolList) {
        return;
    }
    try {
        const response = await fetch('/api/tools');
        if (!response.ok) {
            throw new Error('Не удалось получить каталог');
        }
        const data = await response.json();
        state.toolCatalog = data.tools;
        state.toolIndex = Object.fromEntries(data.tools.map((tool) => [tool.tool_id, tool]));
        renderToolList();
    } catch (error) {
        dom.toolList.textContent = 'Ошибка загрузки каталога.';
        console.error(error);
    }
}

function renderToolList() {
    dom.toolList.innerHTML = '';
    state.toolCatalog.forEach((tool) => {
        const label = document.createElement('label');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.name = 'expected';
        checkbox.value = tool.tool_id;
        checkbox.checked = true;
        checkbox.defaultChecked = true;

        const content = document.createElement('div');
        const title = document.createElement('strong');
        title.textContent = tool.name;
        const description = document.createElement('p');
        description.textContent = tool.description;
        description.classList.add('tool-description');
        content.appendChild(title);
        content.appendChild(description);

        label.appendChild(checkbox);
        label.appendChild(content);
        dom.toolList.appendChild(label);
    });
}

function applySession(session) {
    state.sessionId = session.session_id;
    state.sessionMode = session.mode;
    state.expectedToolIds = session.expected_tool_ids;
    state.threshold = session.threshold;
    state.latestAnalysis = null;

    updateSessionSummaries();
    resetUpload();
    goToStep(2);
}

function resetWizard(silent = false) {
    state.sessionId = null;
    state.sessionMode = null;
    state.expectedToolIds = [];
    state.threshold = 0.9;
    state.latestAnalysis = null;
    state.currentStep = 1;

    dom.sessionForm?.reset();
    dom.sessionForm?.querySelectorAll('input[name="expected"]').forEach((input) => {
        input.checked = true;
        input.defaultChecked = true;
    });
    if (dom.thresholdSlider) {
        dom.thresholdSlider.value = 90;
        dom.thresholdValue.textContent = '90%';
    }
    hideElement(dom.sessionFormStatus);
    resetUpload();
    updateSessionSummaries();
    goToStep(1);
    if (!silent) {
        setStatus('Готов к работе');
    }
}

function goToStep(step) {
    if (!canAccessStep(step)) {
        return;
    }
    state.currentStep = step;
    dom.stepSections.forEach((section) => {
        section.hidden = Number(section.dataset.step) !== step;
    });
    updateStepper();
}

function updateStepper() {
    dom.stepperItems.forEach((item) => {
        const index = Number(item.dataset.stepIndex);
        const isCurrent = index === state.currentStep;
        const isCompleted = index < state.currentStep && canAccessStep(index);
        item.classList.toggle('stepper__item--current', isCurrent);
        item.classList.toggle('stepper__item--done', isCompleted);
        if (isCurrent) {
            item.setAttribute('aria-current', 'step');
        } else {
            item.removeAttribute('aria-current');
        }
    });
}

function canAccessStep(step) {
    if (step <= 1) {
        return true;
    }
    if (step === 2) {
        return Boolean(state.sessionId);
    }
    if (step === 3) {
        return Boolean(state.latestAnalysis);
    }
    return false;
}

function updateSessionSummaries() {
    const hasSession = Boolean(state.sessionId);
    const modeLabel = formatMode(state.sessionMode);
    const thresholdLabel = `${Math.round(state.threshold * 100)}%`;
    const expectedLabel = state.expectedToolIds
        .map((toolId) => state.toolIndex[toolId]?.name || toolId)
        .join(', ');

    const entries = [
        {
            summary: dom.sessionSummary,
            tools: dom.sessionTools,
            id: dom.sessionId,
            mode: dom.sessionMode,
            threshold: dom.sessionThreshold,
            expected: dom.sessionExpected,
        },
        {
            summary: dom.sessionSummaryResults,
            tools: dom.sessionToolsResults,
            id: dom.sessionIdResults,
            mode: dom.sessionModeResults,
            threshold: dom.sessionThresholdResults,
            expected: dom.sessionExpectedResults,
        },
    ];

    entries.forEach((entry) => {
        if (!entry.summary || !entry.tools) {
            return;
        }
        entry.summary.hidden = !hasSession;
        entry.tools.hidden = !hasSession;
        if (!hasSession) {
            return;
        }
        entry.id.textContent = state.sessionId;
        entry.mode.textContent = modeLabel;
        entry.threshold.textContent = `Порог ${thresholdLabel}`;
        entry.expected.textContent = expectedLabel || '—';
    });
}

function handleFileList(fileList) {
    if (!state.token) {
        alert('Сначала войдите в систему.');
        return;
    }
    if (!state.sessionId) {
        alert('Сначала создайте сессию.');
        return;
    }
    if (!fileList?.length) {
        return;
    }
    const file = fileList[0];
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
        alert('Поддерживаются только изображения (JPEG, PNG, WEBP).');
        return;
    }
    previewFile(file);
    uploadFile(file);
}

function previewFile(file) {
    const reader = new FileReader();
    reader.onload = (event) => {
        if (!dom.previewImg || !dom.previewWrapper) {
            return;
        }
        dom.previewImg.src = event.target?.result;
        dom.previewWrapper.hidden = false;
    };
    reader.readAsDataURL(file);
}

function resetUpload() {
    if (dom.fileInput) {
        dom.fileInput.value = '';
    }
    if (dom.previewWrapper) {
        dom.previewWrapper.hidden = true;
    }
    if (dom.previewImg) {
        dom.previewImg.src = '';
    }
    if (dom.analysisSummary) {
        dom.analysisSummary.textContent = 'Нет данных. Загрузите изображение.';
        dom.analysisSummary.className = 'analysis-summary';
    }
    if (dom.analysisContent) {
        dom.analysisContent.hidden = true;
    }
    if (dom.detectedTableBody) {
        dom.detectedTableBody.innerHTML = '';
    }
    dom.missingList?.replaceChildren();
    dom.unexpectedList?.replaceChildren();
    state.latestAnalysis = null;
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file, file.name);
    if (dom.analysisSummary) {
        dom.analysisSummary.textContent = 'Обработка изображения...';
        dom.analysisSummary.className = 'analysis-summary';
    }
    try {
        const result = await apiRequest(`/api/sessions/${state.sessionId}/analyse`, {
            method: 'POST',
            body: formData,
        });
        state.latestAnalysis = result;
        renderAnalysis(result);
        goToStep(3);
    } catch (error) {
        if (dom.analysisSummary) {
            dom.analysisSummary.textContent = `Ошибка: ${error.message}`;
            dom.analysisSummary.className = 'analysis-summary analysis-summary--warn';
        }
        console.error(error);
    }
}

function renderAnalysis(result) {
    if (!dom.analysisContent || !dom.analysisSummary) {
        return;
    }
    const { analysis, session_status: sessionStatus } = result;
    dom.analysisContent.hidden = false;

    const matchPercent = Math.round(analysis.match_ratio * 100);
    if (analysis.below_threshold) {
        dom.analysisSummary.textContent = `Совпадений ${matchPercent}% — требуется ручная сверка.`;
        dom.analysisSummary.className = 'analysis-summary analysis-summary--warn';
    } else {
        dom.analysisSummary.textContent = `Совпадений ${matchPercent}%. Статус: ${sessionStatus}.`;
        dom.analysisSummary.className = 'analysis-summary analysis-summary--ok';
    }

    if (dom.detectedTableBody) {
        dom.detectedTableBody.innerHTML = '';
        analysis.detected.forEach((item) => {
            const row = document.createElement('tr');
            const nameCell = document.createElement('td');
            nameCell.textContent = item.label || (item.tool_id ? (state.toolIndex[item.tool_id]?.name || item.tool_id) : 'Неизвестно');
            const confidenceCell = document.createElement('td');
            const confidencePercent = Math.round(item.confidence * 100);
            confidenceCell.textContent = `${confidencePercent}%`;
            row.appendChild(nameCell);
            row.appendChild(confidenceCell);
            dom.detectedTableBody.appendChild(row);
        });
    }

    renderChipList(dom.missingList, analysis.missing_tool_ids, 'chip chip--danger', 'Все инструменты на месте');
    renderChipList(dom.unexpectedList, analysis.unexpected_labels, 'chip chip--info', 'Посторонних объектов нет');
    updateSessionSummaries();
}

function renderChipList(container, values, className, emptyText) {
    if (!container) {
        return;
    }
    container.innerHTML = '';
    if (!values.length) {
        const span = document.createElement('span');
        span.className = 'chip';
        span.textContent = emptyText;
        container.appendChild(span);
        return;
    }
    values.forEach((value) => {
        const chip = document.createElement('span');
        chip.className = className;
        const readable = state.toolIndex[value]?.name || value;
        chip.textContent = readable;
        container.appendChild(chip);
    });
}

function showFormStatus(message, tone = 'info') {
    if (!dom.sessionFormStatus) {
        return;
    }
    if (!message) {
        hideElement(dom.sessionFormStatus);
        return;
    }
    dom.sessionFormStatus.textContent = message;
    dom.sessionFormStatus.hidden = false;
    dom.sessionFormStatus.className = `form-feedback form-feedback--${tone}`;
}

function setStatus(message) {
    if (dom.status) {
        dom.status.textContent = message;
    }
}

function formatMode(mode) {
    if (mode === 'handout') {
        return 'Режим выдачи';
    }
    if (mode === 'handover') {
        return 'Режим возврата';
    }
    return 'Сессия неактивна';
}

function hideElement(element) {
    if (element) {
        element.hidden = true;
    }
}
