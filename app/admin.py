"""
Настройка FastAPI-Admin для управления данными через веб-интерфейс.

FastAPI-Admin предоставляет административную панель для:
- Управления пользователями
- Просмотра объявлений
- Управления закладками
- Мониторинга задач Celery
"""

from fastapi import FastAPI
from fastapi_admin.app import app as admin_app
from fastapi_admin.providers.login import UsernamePasswordProvider
from fastapi_admin.resources import Model, Link
from fastapi_admin.widgets import filters, displays, inputs
from sqladmin import Admin, ModelView
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.session import get_db
from app.db.models.property import Property
from app.db.models.bookmarks import Bookmark
from app.db.models.ml_price_history import MLPriceHistory


# =============================================================================
# SQLAdmin Views
# =============================================================================

class PropertyAdmin(ModelView):
    """Админка для управления объявлениями."""
    model = Property
    column_list = [
        "id",
        "title",
        "price",
        "rooms",
        "area",
        "city",
        "source",
        "created_at",
    ]
    column_searchable_list = ["title", "city", "source"]
    column_filters = [
        "city",
        "source",
        "price",
        "rooms",
        "created_at",
    ]
    column_editable_list = ["price", "title"]
    form_columns = [
        "title",
        "price",
        "rooms",
        "area",
        "city",
        "district",
        "source",
        "url",
        "description",
    ]


class BookmarkAdmin(ModelView):
    """Админка для управления закладками."""
    model = Bookmark
    column_list = [
        "id",
        "user_id",
        "property_title",
        "bookmark_type",
        "collection_name",
        "created_at",
    ]
    column_searchable_list = ["user_id", "property_title", "collection_name"]
    column_filters = [
        "bookmark_type",
        "collection_name",
        "created_at",
    ]


class MLPriceHistoryAdmin(ModelView):
    """Админка для истории ML предсказаний."""
    model = MLPriceHistory
    column_list = [
        "id",
        "city",
        "rooms",
        "predicted_price",
        "confidence",
        "created_at",
    ]
    column_filters = ["city", "rooms", "created_at"]


# =============================================================================
# Admin App Configuration
# =============================================================================

def create_admin_app() -> FastAPI:
    """
    Создаёт приложение FastAPI-Admin.
    
    Returns:
        FastAPI приложение с админ-панелью
    """
    # Основное приложение
    admin = FastAPI(
        title="RentScout Admin",
        description="Административная панель для управления RentScout",
        version="1.0.0",
    )

    # Инициализация FastAPI-Admin
    admin_app.mount(
        "/admin",
        admin,
        title="RentScout Admin",
        docs_url=None,
        redoc_url=None,
    )

    # Настройка провайдера аутентификации
    admin_app.configure(
        admin_model=None,  # Использовать дефолтную модель админа
        providers=[
            UsernamePasswordProvider(
                login_title="RentScout Admin Login",
                username_label="Username",
                password_label="Password",
                login_logo_url="https://rentscout.dev/logo.png",
            )
        ],
        resources=[
            Link(
                name="Home",
                url="/admin",
                icon="fas fa-home",
            ),
            Link(
                name="API Docs",
                url="/docs",
                icon="fas fa-book",
            ),
            Link(
                name="Grafana",
                url="http://localhost:3001",
                icon="fas fa-chart-line",
            ),
            Link(
                name="Flower (Celery)",
                url="http://localhost:5555",
                icon="fas fa-tasks",
            ),
            Model,
        ],
    )

    return admin


def setup_admin_panel(main_app: FastAPI, db_session: AsyncSession) -> None:
    """
    Настраивает админ-панель для основного приложения.
    
    Args:
        main_app: Основное FastAPI приложение
        db_session: Сессия базы данных
    """
    # Создание SQLAdmin
    admin = Admin(main_app, db_session)

    # Добавление views
    admin.add_view(PropertyAdmin)
    admin.add_view(BookmarkAdmin)
    admin.add_view(MLPriceHistoryAdmin)


# =============================================================================
# Admin Dashboard Widgets
# =============================================================================

ADMIN_DASHBOARD_WIDGETS = [
    {
        "title": "Total Properties",
        "query": "SELECT COUNT(*) FROM properties",
        "type": "stat",
        "icon": "fa-building",
    },
    {
        "title": "Total Users",
        "query": "SELECT COUNT(DISTINCT user_id) FROM bookmarks",
        "type": "stat",
        "icon": "fa-users",
    },
    {
        "title": "Total Bookmarks",
        "query": "SELECT COUNT(*) FROM bookmarks",
        "type": "stat",
        "icon": "fa-bookmark",
    },
    {
        "title": "Recent Properties",
        "query": "SELECT * FROM properties ORDER BY created_at DESC LIMIT 10",
        "type": "table",
        "icon": "fa-list",
    },
    {
        "title": "Top Cities",
        "query": """
            SELECT city, COUNT(*) as count
            FROM properties
            GROUP BY city
            ORDER BY count DESC
            LIMIT 5
        """,
        "type": "chart",
        "icon": "fa-chart-bar",
    },
]


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "PropertyAdmin",
    "BookmarkAdmin",
    "MLPriceHistoryAdmin",
    "create_admin_app",
    "setup_admin_panel",
    "ADMIN_DASHBOARD_WIDGETS",
]
