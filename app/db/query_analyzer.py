"""
Database query optimization and analysis tools.

Provides utilities for analyzing and optimizing database queries using EXPLAIN ANALYZE.
"""
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.utils.logger import logger


class QueryAnalyzer:
    """Analyze database queries for performance optimization."""

    @staticmethod
    async def analyze_query(db: AsyncSession, query: str) -> Dict[str, Any]:
        """
        Analyze a query using EXPLAIN ANALYZE.

        Args:
            db: Database session
            query: SQL query to analyze

        Returns:
            Query analysis results
        """
        start_time = time.time()

        try:
            # Execute EXPLAIN ANALYZE
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS, VERBOSE, JSON) {query}"
            result = await db.execute(text(explain_query))
            analysis = result.fetchall()

            duration = time.time() - start_time

            if analysis:
                return {
                    "status": "success",
                    "query": query,
                    "analysis": analysis[0][0] if analysis else None,
                    "duration_ms": round(duration * 1000, 2),
                }
            else:
                return {
                    "status": "error",
                    "message": "No analysis results",
                    "query": query,
                }
        except Exception as e:
            logger.error(
                f"Error analyzing query: {str(e)}",
                extra={"query": query, "error": str(e)},
            )
            return {
                "status": "error",
                "message": str(e),
                "query": query,
            }

    @staticmethod
    async def analyze_slow_queries(
        db: AsyncSession,
        min_duration_ms: float = 100,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get slowest queries from query log.

        Args:
            db: Database session
            min_duration_ms: Minimum query duration in milliseconds
            limit: Maximum number of queries to return

        Returns:
            List of slow queries
        """
        try:
            # Note: This requires pg_stat_statements extension
            query = text(f"""
                SELECT
                    query,
                    calls,
                    total_time,
                    mean_time,
                    stddev_time,
                    min_time,
                    max_time
                FROM pg_stat_statements
                WHERE mean_time > :min_duration
                ORDER BY mean_time DESC
                LIMIT :limit
            """)

            result = await db.execute(
                query,
                {"min_duration": min_duration_ms, "limit": limit},
            )
            queries = result.fetchall()

            return [
                {
                    "query": q[0],
                    "calls": q[1],
                    "total_time_ms": round(q[2], 2),
                    "mean_time_ms": round(q[3], 2),
                    "stddev_time_ms": round(q[4], 2),
                    "min_time_ms": round(q[5], 2),
                    "max_time_ms": round(q[6], 2),
                }
                for q in queries
            ]
        except Exception as e:
            logger.error(
                f"Error fetching slow queries: {str(e)}",
                extra={"error": str(e)},
            )
            return []

    @staticmethod
    def extract_performance_metrics(analysis: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract key performance metrics from EXPLAIN ANALYZE output.

        Args:
            analysis: EXPLAIN ANALYZE JSON output

        Returns:
            Performance metrics
        """
        try:
            if not analysis or not analysis[0]:
                return {"status": "error", "message": "No analysis data"}

            plan = analysis[0]

            return {
                "status": "success",
                "total_cost": plan.get("Total Cost", 0),
                "planning_time_ms": plan.get("Planning Time", 0),
                "execution_time_ms": plan.get("Execution Time", 0),
                "rows": plan.get("Actual Rows", 0),
                "buffers": plan.get("Buffers", ""),
                "plan_summary": {
                    "node_type": plan.get("Plan", {}).get("Node Type", ""),
                    "rows_per_node": plan.get("Plan", {}).get("Actual Rows", 0),
                },
            }
        except Exception as e:
            logger.error(
                f"Error extracting metrics: {str(e)}",
                extra={"error": str(e)},
            )
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def suggest_indexes(
        db: AsyncSession,
        schema: str = "public",
    ) -> List[Dict[str, Any]]:
        """
        Suggest missing indexes based on query patterns.

        Args:
            db: Database session
            schema: Database schema

        Returns:
            List of suggested indexes
        """
        try:
            query = text(f"""
                SELECT
                    schemaname,
                    tablename,
                    attname,
                    n_distinct,
                    correlation
                FROM pg_stats
                WHERE schemaname = :schema
                    AND n_distinct > 100
                    AND abs(correlation) < 0.1
                ORDER BY n_distinct DESC
            """)

            result = await db.execute(query, {"schema": schema})
            suggestions = result.fetchall()

            return [
                {
                    "schema": s[0],
                    "table": s[1],
                    "column": s[2],
                    "distinct_values": s[3],
                    "correlation": round(s[4], 3),
                    "suggested_index": f"CREATE INDEX idx_{s[1]}_{s[2]} ON {s[0]}.{s[1]} ({s[2]});",
                }
                for s in suggestions
            ]
        except Exception as e:
            logger.error(
                f"Error suggesting indexes: {str(e)}",
                extra={"error": str(e)},
            )
            return []

    @staticmethod
    async def check_table_stats(
        db: AsyncSession,
        schema: str = "public",
    ) -> List[Dict[str, Any]]:
        """
        Check table statistics and bloat.

        Args:
            db: Database session
            schema: Database schema

        Returns:
            Table statistics
        """
        try:
            query = text(f"""
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                    n_live_tup as live_rows,
                    n_dead_tup as dead_rows,
                    last_vacuum,
                    last_autovacuum
                FROM pg_stat_user_tables
                WHERE schemaname = :schema
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """)

            result = await db.execute(query, {"schema": schema})
            stats = result.fetchall()

            return [
                {
                    "schema": s[0],
                    "table": s[1],
                    "total_size": s[2],
                    "live_rows": s[3],
                    "dead_rows": s[4],
                    "last_vacuum": s[5],
                    "last_autovacuum": s[6],
                }
                for s in stats
            ]
        except Exception as e:
            logger.error(
                f"Error checking table stats: {str(e)}",
                extra={"error": str(e)},
            )
            return []
