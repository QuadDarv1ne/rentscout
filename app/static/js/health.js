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
    const statusIcon = isHealthy ? '✅' : '⚠️';
    const statusClass = isHealthy ? 'status-healthy' : 'status-unhealthy';
    
    statusContainer.innerHTML = `
        <div class="status-card ${statusClass}">
            <div class="status-header">
                <span class="status-icon">${statusIcon}</span>
                <h3>Статус системы: ${data.status.toUpperCase()}</h3>
            </div>
            <p>Последнее обновление: ${new Date().toLocaleString('ru-RU')}</p>
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
    
    const statusIcon = isHealthy ? '✅' : '❌';
    const statusClass = isHealthy ? 'status-healthy' : 'status-unhealthy';
    
    card.className = `status-card ${statusClass}`;
    card.innerHTML = `
        <div class="status-header">
            <span class="status-icon">${statusIcon}</span>
            <h4>${formatServiceName(name)}</h4>
        </div>
        <p>Статус: <strong>${statusText}</strong></p>
        ${typeof data === 'object' && data.message ? `<p>${escapeHtml(data.message)}</p>` : ''}
        ${typeof data === 'object' && data.latency ? `<p>Задержка: ${data.latency}ms</p>` : ''}
    `;
    
    return card;
}

function displaySystemInfo(data, container) {
    const infoCards = [];
    
    if (data.version) {
        infoCards.push({
            label: 'Версия',
            value: data.version,
            icon: '📦'
        });
    }
    
    if (data.uptime) {
        infoCards.push({
            label: 'Время работы',
            value: formatUptime(data.uptime),
            icon: '⏱️'
        });
    }
    
    if (data.timestamp) {
        infoCards.push({
            label: 'Время сервера',
            value: new Date(data.timestamp).toLocaleString('ru-RU'),
            icon: '🕐'
        });
    }
    
    if (data.environment) {
        infoCards.push({
            label: 'Окружение',
            value: data.environment,
            icon: '🔧'
        });
    }
    
    container.innerHTML = infoCards.map(card => `
        <div class="info-card">
            <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">${card.icon}</div>
            <div style="font-weight: 600; margin-bottom: 0.25rem;">${card.label}</div>
            <div style="color: var(--text-light);">${card.value}</div>
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
