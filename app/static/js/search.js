// JavaScript для страницы поиска

document.addEventListener('DOMContentLoaded', () => {
    const searchForm = document.getElementById('searchForm');
    const resultsContainer = document.getElementById('results');
    const loadingIndicator = document.getElementById('loading');

    // Загрузка параметров из URL
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('city')) {
        document.getElementById('city').value = urlParams.get('city');
    }
    if (urlParams.has('property_type')) {
        document.getElementById('property_type').value = urlParams.get('property_type');
    }

    // Автоматический поиск при загрузке, если есть параметры
    if (urlParams.toString()) {
        performSearch(Object.fromEntries(urlParams));
    }

    // Обработка отправки формы
    searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(searchForm);
        const searchParams = {};
        
        // Собираем только заполненные поля
        for (let [key, value] of formData.entries()) {
            if (value.trim()) {
                searchParams[key] = value;
            }
        }
        
        await performSearch(searchParams);
    });

    async function performSearch(params) {
        // Показываем индикатор загрузки
        loadingIndicator.style.display = 'block';
        resultsContainer.innerHTML = '';

        try {
            // Формируем URL для API запроса
            const queryString = new URLSearchParams(params).toString();
            const response = await fetch(`/api/properties/search?${queryString}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            displayResults(data);
            
        } catch (error) {
            console.error('Ошибка при поиске:', error);
            resultsContainer.innerHTML = `
                <div style="padding: 2rem; text-align: center; color: var(--danger-color);">
                    <h3>Произошла ошибка при поиске</h3>
                    <p>${error.message}</p>
                </div>
            `;
        } finally {
            loadingIndicator.style.display = 'none';
        }
    }

    function displayResults(data) {
        if (!data.results || data.results.length === 0) {
            resultsContainer.innerHTML = `
                <div class="alert alert-info text-center" role="alert">
                    <i class="bi bi-info-circle fs-1 d-block mb-3"></i>
                    <h4>Ничего не найдено</h4>
                    <p class="mb-0">Попробуйте изменить параметры поиска</p>
                </div>
            `;
            return;
        }

        // Заголовок с количеством результатов
        const header = document.createElement('div');
        header.className = 'alert alert-success mb-4';
        header.innerHTML = `
            <i class="bi bi-check-circle me-2"></i>
            <strong>Найдено объявлений: ${data.total || data.results.length}</strong>
            ${data.took ? `<span class="text-muted ms-2">(${data.took}ms)</span>` : ''}
        `;
        resultsContainer.appendChild(header);

        // Отображаем карточки объявлений
        data.results.forEach(property => {
            const card = createPropertyCard(property);
            resultsContainer.appendChild(card);
        });
    }

    function createPropertyCard(property) {
        const card = document.createElement('div');
        card.className = 'property-card shadow-sm';
        
        // Формируем HTML карточки
        card.innerHTML = `
            <div class="property-header">
                <div>
                    <h3 class="property-title">${escapeHtml(property.title || 'Без названия')}</h3>
                    <span class="property-source badge bg-primary">${escapeHtml(property.source || 'Неизвестный источник')}</span>
                </div>
                <div class="property-price">${formatPrice(property.price)}</div>
            </div>
            
            <div class="property-details">
                ${property.city ? `<div class="property-detail"><i class="bi bi-geo-alt text-primary me-1"></i>${escapeHtml(property.city)}</div>` : ''}
                ${property.property_type ? `<div class="property-detail"><i class="bi bi-house text-primary me-1"></i>${escapeHtml(property.property_type)}</div>` : ''}
                ${property.rooms ? `<div class="property-detail"><i class="bi bi-door-closed text-primary me-1"></i>${property.rooms} комн.</div>` : ''}
                ${property.area ? `<div class="property-detail"><i class="bi bi-bounding-box text-primary me-1"></i>${property.area} м²</div>` : ''}
            </div>
            
            ${property.description ? `
                <div class="mb-3 text-muted">
                    ${escapeHtml(property.description.substring(0, 200))}${property.description.length > 200 ? '...' : ''}
                </div>
            ` : ''}
            
            ${property.url ? `
                <a href="${escapeHtml(property.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-outline-primary">
                    <i class="bi bi-box-arrow-up-right me-2"></i>Посмотреть объявление
                </a>
            ` : ''}
            
            ${property.metadata ? `
                <div class="mt-3 small text-muted">
                    <i class="bi bi-clock me-1"></i>Обновлено: ${new Date(property.metadata.last_updated || property.metadata.posted_at).toLocaleDateString('ru-RU')}
                </div>
            ` : ''}
        `;
        
        return card;
    }

    function formatPrice(price) {
        if (!price) return 'Цена не указана';
        return new Intl.NumberFormat('ru-RU', {
            style: 'currency',
            currency: 'RUB',
            minimumFractionDigits: 0
        }).format(price);
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Сброс формы
    const resetButton = document.querySelector('button[type="reset"]');
    if (resetButton) {
        resetButton.addEventListener('click', () => {
            resultsContainer.innerHTML = '';
            // Очищаем URL параметры
            window.history.replaceState({}, '', window.location.pathname);
        });
    }
});
