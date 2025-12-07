// Главный JavaScript файл для домашней страницы

document.addEventListener('DOMContentLoaded', () => {
    // Анимация появления элементов при прокрутке
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

    // Обработка формы быстрого поиска
    const quickSearchForm = document.getElementById('quickSearchForm');
    if (quickSearchForm) {
        quickSearchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            
            const city = document.getElementById('city').value;
            const propertyType = document.getElementById('property_type').value;
            
            // Формируем URL с параметрами
            const params = new URLSearchParams();
            if (city) params.append('city', city);
            if (propertyType) params.append('property_type', propertyType);
            
            // Переходим на страницу поиска с параметрами
            window.location.href = `/search?${params.toString()}`;
        });
    }

    // Плавная прокрутка для якорных ссылок
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

    // Анимация счетчиков статистики
    const animateCounter = (element, target, duration = 2000) => {
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
    };

    // Запускаем анимацию счетчиков при загрузке
    const statNumbers = document.querySelectorAll('.stat-number');
    statNumbers.forEach(stat => {
        const value = stat.textContent.replace(/\D/g, '');
        if (value) {
            stat.textContent = '0';
            setTimeout(() => {
                animateCounter(stat, parseInt(value), 1500);
            }, 500);
        }
    });
});
