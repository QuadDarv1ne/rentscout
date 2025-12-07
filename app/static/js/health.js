// JavaScript для страницы статуса системы

document.addEventListener('DOMContentLoaded', () => {
    loadHealthStatus();
    
    // Автоматическое обновление каждые 30 секунд
    setInterval(loadHealthStatus, 30000);
});

async function loadHealthStatus() {
    const statusContainer = document.getElementById('healthStatus');
    const systemInfoContainer = document.getElementById('systemInfo');
    
    try {
        const response = await fetch('/api/health');
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        displayHealthStatus(data, statusContainer, systemInfoContainer);
        
    } catch (error) {
        console.error('Ошибка при получении статуса:', error);
        statusContainer.innerHTML = `
            <div class="status-card status-unhealthy">
                <div class="status-header">
                    <span class="status-icon">❌</span>
                    <h3>Ошибка подключения</h3>
                </div>
                <p>${error.message}</p>
            </div>
        `;
    }
}

function displayHealthStatus(data, statusContainer, systemInfoContainer) {
    // Общий статус
    const isHealthy = data.status === 'healthy' || data.status === 'ok';
    const statusIcon = isHealthy ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill';
    const statusClass = isHealthy ? 'alert-success' : 'alert-warning';
    
    statusContainer.innerHTML = `
        <div class="alert ${statusClass} d-flex align-items-center" role="alert">
            <i class="bi ${statusIcon} fs-3 me-3"></i>
            <div>
                <h4 class="alert-heading mb-1">Статус системы: ${data.status.toUpperCase()}</h4>
                <p class="mb-0 small">Последнее обновление: ${new Date().toLocaleString('ru-RU')}</p>
            </div>
        </div>
    `;

    // Подробная информация о компонентах
    if (data.services || data.dependencies) {
        const services = data.services || data.dependencies || {};
        
        Object.entries(services).forEach(([serviceName, serviceData]) => {
            const serviceCard = createServiceCard(serviceName, serviceData);
            statusContainer.appendChild(serviceCard);
        });
    }

    // Системная информация
    if (data.version || data.uptime || data.timestamp) {
        displaySystemInfo(data, systemInfoContainer);
    }
}

function createServiceCard(name, data) {
    const card = document.createElement('div');
    
    let isHealthy = false;
    let statusText = 'unknown';
    
    if (typeof data === 'object') {
        isHealthy = data.status === 'healthy' || data.status === 'connected' || data.status === 'ok';
        statusText = data.status || 'unknown';
    } else if (typeof data === 'string') {
        isHealthy = data === 'healthy' || data === 'connected' || data === 'ok';
        statusText = data;
    }
    
    const statusIcon = isHealthy ? 'bi-check-circle-fill text-success' : 'bi-x-circle-fill text-danger';
    const borderClass = isHealthy ? 'border-success' : 'border-danger';
    
    card.className = `card mb-3 ${borderClass}`;
    card.innerHTML = `
        <div class="card-body">
            <div class="d-flex align-items-center mb-2">
                <i class="bi ${statusIcon} fs-4 me-3"></i>
                <h5 class="card-title mb-0">${formatServiceName(name)}</h5>
            </div>
            <p class="card-text">
                <span class="badge ${isHealthy ? 'bg-success' : 'bg-danger'}">${statusText}</span>
                ${typeof data === 'object' && data.message ? `<br><small class="text-muted">${escapeHtml(data.message)}</small>` : ''}
                ${typeof data === 'object' && data.latency ? `<br><small class="text-muted">Задержка: ${data.latency}ms</small>` : ''}
            </p>
        </div>
    `;
    
    return card;
}

function displaySystemInfo(data, container) {
    const infoCards = [];
    
    if (data.version) {
        infoCards.push({
            label: 'Версия',
            value: data.version,
            icon: 'bi-box'
        });
    }
    
    if (data.uptime) {
        infoCards.push({
            label: 'Время работы',
            value: formatUptime(data.uptime),
            icon: 'bi-clock'
        });
    }
    
    if (data.timestamp) {
        infoCards.push({
            label: 'Время сервера',
            value: new Date(data.timestamp).toLocaleString('ru-RU'),
            icon: 'bi-calendar'
        });
    }
    
    if (data.environment) {
        infoCards.push({
            label: 'Окружение',
            value: data.environment,
            icon: 'bi-gear'
        });
    }
    
    container.innerHTML = infoCards.map(card => `
        <div class="col-md-6 col-lg-3">
            <div class="card border-0 shadow-sm">
                <div class="card-body text-center">
                    <i class="bi ${card.icon} fs-1 text-primary mb-3"></i>
                    <h6 class="card-subtitle mb-2 text-muted">${card.label}</h6>
                    <p class="card-text fw-bold">${card.value}</p>
                </div>
            </div>
        </div>
    `).join('');
}

function formatServiceName(name) {
    // Форматируем имя сервиса для отображения
    return name
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase());
}

function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    const parts = [];
    if (days > 0) parts.push(`${days}д`);
    if (hours > 0) parts.push(`${hours}ч`);
    if (minutes > 0) parts.push(`${minutes}м`);
    
    return parts.join(' ') || '< 1м';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
