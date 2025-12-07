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
                <div style="padding: 2rem; text-align: center;">
                    <h3>Ничего не найдено</h3>
                    <p>Попробуйте изменить параметры поиска</p>
                </div>
            `;
            return;
        }

        // Заголовок с количеством результатов
        const header = document.createElement('div');
        header.style.marginBottom = '1.5rem';
        header.innerHTML = `
            <h3>Найдено объявлений: ${data.total || data.results.length}</h3>
            ${data.took ? `<p style="color: var(--text-light);">Время поиска: ${data.took}ms</p>` : ''}
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
        card.className = 'property-card';
        
        // Формируем HTML карточки
        card.innerHTML = `
            <div class="property-header">
                <div>
                    <h3 class="property-title">${escapeHtml(property.title || 'Без названия')}</h3>
                    <span class="property-source">${escapeHtml(property.source || 'Неизвестный источник')}</span>
                </div>
                <div class="property-price">${formatPrice(property.price)}</div>
            </div>
            
            <div class="property-details">
                ${property.city ? `<div class="property-detail">📍 ${escapeHtml(property.city)}</div>` : ''}
                ${property.property_type ? `<div class="property-detail">🏠 ${escapeHtml(property.property_type)}</div>` : ''}
                ${property.rooms ? `<div class="property-detail">🛏️ ${property.rooms} комн.</div>` : ''}
                ${property.area ? `<div class="property-detail">📐 ${property.area} м²</div>` : ''}
            </div>
            
            ${property.description ? `
                <div style="margin: 1rem 0; color: var(--text-light);">
                    ${escapeHtml(property.description.substring(0, 200))}${property.description.length > 200 ? '...' : ''}
                </div>
            ` : ''}
            
            ${property.url ? `
                <a href="${escapeHtml(property.url)}" target="_blank" class="property-link">
                    Посмотреть объявление →
                </a>
            ` : ''}
            
            ${property.metadata ? `
                <div style="margin-top: 1rem; font-size: 0.85rem; color: var(--text-light);">
                    Обновлено: ${new Date(property.metadata.last_updated || property.metadata.posted_at).toLocaleDateString('ru-RU')}
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
