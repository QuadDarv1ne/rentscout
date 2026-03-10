"""Add materialized views for performance optimization

Revision ID: 2026_03_10_materialized_views
Revises: 2026_02_21_optimized_indexes
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '2026_03_10_materialized_views'
down_revision = '2026_02_21_optimized_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create materialized views for common queries."""

    # Materialized view for property statistics by city and district
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_property_stats_by_location AS
        SELECT
            city,
            district,
            source,
            COUNT(*) as property_count,
            AVG(price) as avg_price,
            MIN(price) as min_price,
            MAX(price) as max_price,
            AVG(area) as avg_area,
            AVG(rooms) as avg_rooms,
            AVG(price / NULLIF(area, 0)) as avg_price_per_sqm,
            COUNT(CASE WHEN is_active = true THEN 1 END) as active_count,
            COUNT(CASE WHEN is_verified = true THEN 1 END) as verified_count
        FROM properties
        WHERE is_active = true
        GROUP BY city, district, source
        WITH DATA;
    """)

    # Index on the materialized view
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_stats_location ON mv_property_stats_by_location(city, district);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_stats_source ON mv_property_stats_by_location(source);")

    # Materialized view for price trends by day
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_price_trends_daily AS
        SELECT
            DATE(created_at) as date,
            city,
            rooms,
            COUNT(*) as property_count,
            AVG(price) as avg_price,
            MIN(price) as min_price,
            MAX(price) as max_price,
            AVG(area) as avg_area,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) as median_price
        FROM properties
        WHERE is_active = true
        GROUP BY DATE(created_at), city, rooms
        WITH DATA;
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_trends_date ON mv_price_trends_daily(date);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_trends_city ON mv_price_trends_daily(city);")

    # Materialized view for popular searches
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_popular_searches AS
        SELECT
            city,
            property_type,
            DATE(searched_at) as search_date,
            COUNT(*) as search_count,
            AVG(results_count) as avg_results,
            COUNT(DISTINCT ip_address) as unique_users
        FROM search_queries
        GROUP BY city, property_type, DATE(searched_at)
        WITH DATA;
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_searches_city ON mv_popular_searches(city);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_searches_date ON mv_popular_searches(search_date);")

    # Materialized view for property views analytics
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_property_views_daily AS
        SELECT
            pv.property_id,
            DATE(pv.viewed_at) as view_date,
            COUNT(*) as view_count,
            COUNT(DISTINCT pv.ip_address) as unique_visitors
        FROM property_views pv
        GROUP BY pv.property_id, DATE(pv.viewed_at)
        WITH DATA;
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_views_property ON mv_property_views_daily(property_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_views_date ON mv_property_views_daily(view_date);")


def downgrade() -> None:
    """Drop materialized views."""

    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_property_views_daily;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_popular_searches;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_price_trends_daily;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_property_stats_by_location;")
