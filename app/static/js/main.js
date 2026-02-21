// Главный JavaScript файл для домашней страницы

document.addEventListener('DOMContentLoaded', () => {
    // Проверка статуса API
    checkAPIStatus();
    
    // Загрузка статистики
    loadStatistics();
    
    // Анимация появления элементов при прокрутке
    initScrollAnimations();
    
    // Обработка формы быстрого поиска
    initQuickSearch();
    
    // Плавная прокрутка для якорных ссылок
    initSmoothScroll();
    
    // Анимация счетчиков статистики
    animateCounters();
});

// Проверка статуса API
async function checkAPIStatus() {
    const badge = document.getElementById('apiStatusBadge');
    if (!badge) return;
    
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        
        if (data.status === 'healthy') {
            badge.innerHTML = `
                <span class="badge bg-success px-3 py-2">
                    <i class="bi bi-check-circle-fill me-2"></i>API работает
                </span>
            `;
        } else {
            badge.innerHTML = `
                <span class="badge bg-warning px-3 py-2">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>API частично доступен
                </span>
            `;
        }
    } catch (error) {
        badge.innerHTML = `
            <span class="badge bg-danger px-3 py-2">
                <i class="bi bi-x-circle-fill me-2"></i>API недоступен
            </span>
        `;
    }
}

// Загрузка статистики
async function loadStatistics() {
    try {
        // Попытка получить количество объявлений
        const response = await fetch('/api/db/properties?limit=1');
        if (response.ok) {
            const data = await response.json();
            const totalElement = document.getElementById('totalProperties');
            if (totalElement && data.total) {
                animateCounter(totalElement, data.total, 2000);
            }
        }
    } catch (error) {
        console.log('Статистика недоступна:', error);
    }
}

// Анимация появления элементов при прокрутке
function initScrollAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Наблюдаем за карточками функций
    document.querySelectorAll('.feature-card, .api-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.6s, transform 0.6s';
        observer.observe(card);
    });
}

// Обработка формы быстрого поиска
function initQuickSearch() {
    const quickSearchForm = document.getElementById('quickSearchForm');
    if (!quickSearchForm) return;
    
    quickSearchForm.addEventListener('submit', (e) => {
        e.preventDefault();
        
        const city = document.getElementById('city').value;
        const propertyType = document.getElementById('property_type').value;
        const maxPrice = document.getElementById('max_price').value;
        
        // Формируем URL с параметрами
        const params = new URLSearchParams();
        if (city) params.append('city', city);
        if (propertyType) params.append('property_type', propertyType);
        if (maxPrice) params.append('max_price', maxPrice);
        
        // Переходим на страницу поиска с параметрами
        window.location.href = `/search?${params.toString()}`;
    });
}

// Плавная прокрутка для якорных ссылок
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// Анимация счетчиков статистики
function animateCounters() {
    const statNumbers = document.querySelectorAll('.stat-number[data-target]');
    
    statNumbers.forEach(stat => {
        const target = parseInt(stat.getAttribute('data-target'));
        if (target) {
            stat.textContent = '0';
            setTimeout(() => {
                animateCounter(stat, target, 1500);
            }, 500);
        }
    });
}

// Функция анимации счетчика
function animateCounter(element, target, duration = 2000) {
    const start = 0;
    const increment = target / (duration / 16);
    let current = start;
    
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            element.textContent = target;
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(current);
        }
    }, 16);
}

// Обработка ошибок загрузки изображений
document.addEventListener('error', (e) => {
    if (e.target.tagName === 'IMG') {
        e.target.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🏠</text></svg>';
    }
}, true);
