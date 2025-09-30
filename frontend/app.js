const state = {
    toolCatalog: [],
    toolIndex: {},
    sessionId: null,
    sessionMode: null,
    expectedToolIds: [],
    threshold: 0.9,
    latestAnalysis: null,
};

const dom = {
    status: document.getElementById('system-status'),
    toolList: document.getElementById('tool-list'),
    sessionForm: document.getElementById('session-form'),
    thresholdSlider: document.getElementById('threshold'),
    thresholdValue: document.getElementById('threshold-value'),
    sessionInfoCard: document.getElementById('session-info'),
    sessionId: document.getElementById('session-id'),
    sessionMode: document.getElementById('session-mode'),
    sessionExpected: document.getElementById('session-expected'),
    sessionThreshold: document.getElementById('session-threshold'),
    dropzone: document.getElementById('dropzone'),
    selectFileButton: document.getElementById('select-file'),
    fileInput: document.getElementById('file-input'),
    previewWrapper: document.getElementById('image-preview'),
    previewImg: document.getElementById('preview-img'),
    resetUpload: document.getElementById('reset-upload'),
    captureCard: document.getElementById('capture-area'),
    analysisCard: document.getElementById('analysis-area'),
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
    fetchToolCatalog();
}

function setupThresholdSlider() {
    dom.thresholdSlider.addEventListener('input', () => {
        const value = Number(dom.thresholdSlider.value);
        dom.thresholdValue.textContent = `${value}%`;
    });
}

function attachFormHandlers() {
    dom.sessionForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!state.toolCatalog.length) {
            alert('Каталог инструментов ещё загружается.');
            return;
        }
        const formData = new FormData(dom.sessionForm);
        const mode = formData.get('mode');
        const thresholdPercent = Number(formData.get('threshold'));
        const threshold = Number((thresholdPercent / 100).toFixed(2));
        const expectedTools = Array.from(dom.sessionForm.querySelectorAll('input[name="expected"]:checked'))
            .map((input) => input.value);
        if (!expectedTools.length) {
            alert('Выберите хотя бы один инструмент из списка.');
            return;
        }
        try {
            dom.status.textContent = 'Создание сессии...';
            const payload = {
                mode,
                expected_tool_ids: expectedTools,
                threshold,
            };
            const response = await fetch('/api/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                throw new Error('Не удалось создать сессию');
            }
            const session = await response.json();
            applySession(session);
            dom.status.textContent = 'Сессия активна';
        } catch (error) {
            console.error(error);
            dom.status.textContent = 'Ошибка: ' + error.message;
        }
    });
}

function attachUploadHandlers() {
    dom.selectFileButton.addEventListener('click', () => dom.fileInput.click());
    dom.fileInput.addEventListener('change', () => handleFileList(dom.fileInput.files));
    dom.resetUpload.addEventListener('click', resetUpload);

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

async function fetchToolCatalog() {
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

    dom.sessionInfoCard.hidden = false;
    dom.captureCard.hidden = false;
    dom.analysisCard.hidden = false;

    dom.sessionId.textContent = session.session_id;
    dom.sessionMode.textContent = session.mode === 'handout' ? 'Выдача' : 'Возврат';
    dom.sessionExpected.textContent = state.expectedToolIds
        .map((toolId) => state.toolIndex[toolId]?.name || toolId)
        .join(', ');
    dom.sessionThreshold.textContent = `${Math.round(state.threshold * 100)}%`;

    resetUpload();
}

function handleFileList(fileList) {
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
        dom.previewImg.src = event.target?.result;
        dom.previewWrapper.hidden = false;
    };
    reader.readAsDataURL(file);
}

function resetUpload() {
    dom.fileInput.value = '';
    dom.previewWrapper.hidden = true;
    dom.previewImg.src = '';
    dom.analysisSummary.textContent = 'Нет данных. Загрузите изображение.';
    dom.analysisSummary.className = 'analysis-summary';
    dom.analysisContent.hidden = true;
    dom.detectedTableBody.innerHTML = '';
    dom.missingList.innerHTML = '';
    dom.unexpectedList.innerHTML = '';
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file, file.name);
    dom.analysisSummary.textContent = 'Обработка изображения...';
    dom.analysisSummary.className = 'analysis-summary';
    try {
        const response = await fetch(`/api/sessions/${state.sessionId}/analyse`, {
            method: 'POST',
            body: formData,
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || 'Ошибка анализа.');
        }
        const result = await response.json();
        state.latestAnalysis = result;
        renderAnalysis(result);
    } catch (error) {
        dom.analysisSummary.textContent = `Ошибка: ${error.message}`;
        dom.analysisSummary.className = 'analysis-summary analysis-summary--warn';
        console.error(error);
    }
}

function renderAnalysis(result) {
    const { analysis, session_status: sessionStatus } = result;
    dom.analysisContent.hidden = false;

    const matchPercent = Math.round(analysis.match_ratio * 100);
    if (analysis.below_threshold) {
        dom.analysisSummary.textContent = `Совпадений ${matchPercent}% — требуется ручной пересчет.`;
        dom.analysisSummary.className = 'analysis-summary analysis-summary--warn';
    } else {
        dom.analysisSummary.textContent = `Совпадений ${matchPercent}%. Сессия: ${sessionStatus}.`;
        dom.analysisSummary.className = 'analysis-summary analysis-summary--ok';
    }

    dom.detectedTableBody.innerHTML = '';
    analysis.detected.forEach((item) => {
        const row = document.createElement('tr');
        const nameCell = document.createElement('td');
        nameCell.textContent = item.label || (item.tool_id ? item.tool_id : 'Неизвестно');
        const confidenceCell = document.createElement('td');
        const confidencePercent = Math.round(item.confidence * 100);
        confidenceCell.textContent = `${confidencePercent}%`;
        row.appendChild(nameCell);
        row.appendChild(confidenceCell);
        dom.detectedTableBody.appendChild(row);
    });

    renderChipList(dom.missingList, analysis.missing_tool_ids, 'chip chip--danger', 'Все инструменты на месте');
    renderChipList(dom.unexpectedList, analysis.unexpected_labels, 'chip chip--info', 'Посторонних объектов нет');
}

function renderChipList(container, values, className, emptyText) {
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
