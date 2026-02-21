"""
Add optimized indexes and statistics tables

Revision ID: 2026_02_21_optimized_indexes
Revises: 2025_12_11_1445-optimize_database_indexes_and_columns
Create Date: 2026-02-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2026_02_21_optimized_indexes'
down_revision: Union[str, None] = '2025_12_11_1445-optimize_database_indexes_and_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавить оптимизированные индексы и таблицы."""

    # ========================================================================
    # 1. Составные индексы для поиска (property_search)
    # ========================================================================

    # Индекс для поиска по городу и цене
    op.create_index(
        'idx_properties_city_price',
        'properties',
        ['city', 'price'],
        unique=False,
        if_not_exists=True
    )

    # Индекс для поиска по городу и комнатам
    op.create_index(
        'idx_properties_city_rooms',
        'properties',
        ['city', 'rooms'],
        unique=False,
        if_not_exists=True
    )

    # Индекс для поиска по городу и площади
    op.create_index(
        'idx_properties_city_area',
        'properties',
        ['city', 'area'],
        unique=False,
        if_not_exists=True
    )

    # Индекс для фильтрации по источнику и дате
    op.create_index(
        'idx_properties_source_first_seen',
        'properties',
        ['source', 'first_seen'],
        unique=False,
        if_not_exists=True
    )

    # ========================================================================
    # 2. Геосpatial индексы (для поиска по местоположению)
    # ========================================================================

    # Индекс для гео-поиска (широта/долгота)
    op.create_index(
        'idx_properties_location',
        'properties',
        ['latitude', 'longitude'],
        unique=False,
        if_not_exists=True
    )

    # ========================================================================
    # 3. Индексы для аналитики и отчётов
    # ========================================================================

    # Индекс для статистики по городам
    op.create_index(
        'idx_properties_city_active',
        'properties',
        ['city', 'is_active'],
        unique=False,
        if_not_exists=True
    )

    # Индекс для анализа цен по датам
    op.create_index(
        'idx_property_price_history_property_date',
        'property_price_history',
        ['property_id', 'changed_at'],
        unique=False,
        if_not_exists=True
    )

    # ========================================================================
    # 4. Таблица статистики поиска (search_analytics)
    # ========================================================================

    op.create_table(
        'search_analytics',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('search_query', sa.Text(), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('min_price', sa.Integer(), nullable=True),
        sa.Column('max_price', sa.Integer(), nullable=True),
        sa.Column('min_rooms', sa.Integer(), nullable=True),
        sa.Column('max_rooms', sa.Integer(), nullable=True),
        sa.Column('results_count', sa.Integer(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(
        'idx_search_analytics_city_created',
        'search_analytics',
        ['city', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    op.create_index(
        'idx_search_analytics_created',
        'search_analytics',
        ['created_at'],
        unique=False,
        if_not_exists=True
    )

    # ========================================================================
    # 5. Таблица метрик производительности парсеров (parser_metrics)
    # ========================================================================

    op.create_table(
        'parser_metrics',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('parser_name', sa.String(length=100), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('properties_found', sa.Integer(), nullable=True),
        sa.Column('parse_time_ms', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('circuit_breaker_state', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(
        'idx_parser_metrics_name_created',
        'parser_metrics',
        ['parser_name', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    # ========================================================================
    # 6. Таблица кэш-метрик (cache_metrics)
    # ========================================================================

    op.create_table(
        'cache_metrics',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('cache_key', sa.String(length=500), nullable=False),
        sa.Column('operation', sa.String(length=50), nullable=False),  # hit, miss, set, delete
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('data_size_bytes', sa.Integer(), nullable=True),
        sa.Column('ttl_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(
        'idx_cache_metrics_operation_created',
        'cache_metrics',
        ['operation', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    # ========================================================================
    # 7. Полнотекстовый индекс для поиска по описанию
    # ========================================================================

    # Добавляем колонку для полнотекстового поиска если её нет
    op.add_column(
        'properties',
        sa.Column('search_vector', sa.TSVector(), nullable=True)
    )

    # Создаём полнотекстовый индекс
    op.create_index(
        'idx_properties_search_vector',
        'properties',
        ['search_vector'],
        unique=False,
        postgresql_using='gin',
        if_not_exists=True
    )

    # Триггер для автоматического обновления search_vector
    op.execute("""
        CREATE OR REPLACE FUNCTION update_properties_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('russian', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('russian', COALESCE(NEW.description, '')), 'B') ||
                setweight(to_tsvector('russian', COALESCE(NEW.city, '')), 'C') ||
                setweight(to_tsvector('russian', COALESCE(NEW.district, '')), 'D');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER update_properties_search_vector_trigger
        BEFORE INSERT OR UPDATE ON properties
        FOR EACH ROW
        EXECUTE FUNCTION update_properties_search_vector();
    """)

    # Обновляем существующие записи
    op.execute("""
        UPDATE properties
        SET search_vector =
            setweight(to_tsvector('russian', COALESCE(title, '')), 'A') ||
            setweight(to_tsvector('russian', COALESCE(description, '')), 'B') ||
            setweight(to_tsvector('russian', COALESCE(city, '')), 'C') ||
            setweight(to_tsvector('russian', COALESCE(district, '')), 'D')
        WHERE search_vector IS NULL;
    """)


def downgrade() -> None:
    """Откатить изменения."""

    # Удаляем триггер и функцию
    op.execute("DROP TRIGGER IF EXISTS update_properties_search_vector_trigger ON properties;")
    op.execute("DROP FUNCTION IF EXISTS update_properties_search_vector();")

    # Удаляем индексы
    op.drop_index('idx_properties_city_price', table_name='properties', if_exists=True)
    op.drop_index('idx_properties_city_rooms', table_name='properties', if_exists=True)
    op.drop_index('idx_properties_city_area', table_name='properties', if_exists=True)
    op.drop_index('idx_properties_source_first_seen', table_name='properties', if_exists=True)
    op.drop_index('idx_properties_location', table_name='properties', if_exists=True)
    op.drop_index('idx_properties_city_active', table_name='properties', if_exists=True)
    op.drop_index('idx_property_price_history_property_date', table_name='property_price_history', if_exists=True)
    op.drop_index('idx_properties_search_vector', table_name='properties', if_exists=True)
    op.drop_index('idx_search_analytics_city_created', table_name='search_analytics', if_exists=True)
    op.drop_index('idx_search_analytics_created', table_name='search_analytics', if_exists=True)
    op.drop_index('idx_parser_metrics_name_created', table_name='parser_metrics', if_exists=True)
    op.drop_index('idx_cache_metrics_operation_created', table_name='cache_metrics', if_exists=True)

    # Удаляем колонку
    op.drop_column('properties', 'search_vector')

    # Удаляем таблицы
    op.drop_table('cache_metrics')
    op.drop_table('parser_metrics')
    op.drop_table('search_analytics')
