"""
Duplicate detection and analytics API endpoints.

Provides endpoints for analyzing duplicates, running deduplication,
and monitoring data quality.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.utils.deduplication import (
    duplicate_detector,
    dedup_analyzer,
    DeduplicationStrategy
)
from app.utils.logger import logger

router = APIRouter(prefix="/api/duplicates", tags=["duplicates"])


@router.get("/health")
async def duplicates_health() -> Dict[str, str]:
    """
    Check duplicate detection system health.
    
    Returns:
        - status: System status
        - duplicates_tracked: Number of duplicates in history
    """
    return {
        "status": "operational",
        "duplicates_tracked": len(duplicate_detector.detected_duplicates),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/statistics")
async def get_duplicate_statistics() -> Dict[str, Any]:
    """
    Get comprehensive duplicate detection statistics.
    
    Returns:
        - total_duplicates: Total duplicates detected
        - duplicates_by_source_pair: Duplicates grouped by source pairs
        - average_similarity: Average similarity score
        - exact_matches: Count of exact duplicates
        - fuzzy_matches: Count of fuzzy matches
    """
    try:
        stats = duplicate_detector.get_statistics()
        return {
            "statistics": stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get duplicate statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get duplicate statistics")


@router.get("/by-sources")
async def get_duplicates_by_sources(
    source1: str = Query(...),
    source2: str = Query(...),
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """
    Get duplicates between two specific sources.
    
    Args:
        source1: First source name
        source2: Second source name
        limit: Maximum duplicates to return
    
    Returns:
        List of duplicates between sources
    """
    try:
        filtered = [
            d for d in duplicate_detector.detected_duplicates
            if (d.source1 == source1 and d.source2 == source2) or
               (d.source1 == source2 and d.source2 == source1)
        ]
        
        # Sort by similarity descending
        filtered.sort(key=lambda d: d.similarity_score, reverse=True)
        
        return {
            "source1": source1,
            "source2": source2,
            "duplicate_count": len(filtered),
            "duplicates": [d.to_dict() for d in filtered[:limit]],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get duplicates by sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to get duplicates by sources")


@router.get("/by-similarity")
async def get_duplicates_by_similarity(
    min_score: float = Query(0.85, ge=0, le=1),
    max_score: float = Query(1.0, ge=0, le=1),
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """
    Get duplicates within similarity score range.
    
    Args:
        min_score: Minimum similarity score (0-1)
        max_score: Maximum similarity score (0-1)
        limit: Maximum duplicates to return
    
    Returns:
        List of duplicates within similarity range
    """
    try:
        if min_score > max_score:
            raise HTTPException(
                status_code=400,
                detail="min_score must be less than or equal to max_score"
            )
        
        filtered = [
            d for d in duplicate_detector.detected_duplicates
            if min_score <= d.similarity_score <= max_score
        ]
        
        # Sort by similarity descending
        filtered.sort(key=lambda d: d.similarity_score, reverse=True)
        
        return {
            "similarity_range": {
                "min": min_score,
                "max": max_score
            },
            "count": len(filtered),
            "duplicates": [d.to_dict() for d in filtered[:limit]],
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get duplicates by similarity: {e}")
        raise HTTPException(status_code=500, detail="Failed to get duplicates by similarity")


@router.get("/analysis")
async def get_deduplication_analysis(
    original_count: int = Query(..., ge=1),
    unique_count: int = Query(..., ge=0)
) -> Dict[str, Any]:
    """
    Analyze deduplication effectiveness.
    
    Args:
        original_count: Count before deduplication
        unique_count: Count after deduplication
    
    Returns:
        Deduplication effectiveness analysis
    """
    try:
        if unique_count > original_count:
            raise HTTPException(
                status_code=400,
                detail="unique_count cannot exceed original_count"
            )
        
        impact = dedup_analyzer.analyze_deduplication_impact(
            original_count,
            unique_count
        )
        
        recommendations = dedup_analyzer.get_deduplication_recommendations(
            {'exact_matches': 0, 'average_similarity': 0.9, **impact},
            []
        )
        
        return {
            "analysis": impact,
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze deduplication: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze deduplication")


@router.post("/run-analysis")
async def run_duplicate_analysis(
    strategy: str = Query("hybrid", enum=["exact", "fuzzy", "hybrid"])
) -> Dict[str, Any]:
    """
    Run duplicate detection analysis on current data.
    
    Args:
        strategy: Deduplication strategy to use
    
    Returns:
        Analysis results and statistics
    """
    try:
        stats = duplicate_detector.get_statistics()
        
        strategy_enum = DeduplicationStrategy(strategy)
        
        return {
            "analysis": {
                "strategy": strategy,
                "statistics": stats,
                "detection_count": len(duplicate_detector.detected_duplicates),
            },
            "recommendations": dedup_analyzer.get_deduplication_recommendations(
                stats,
                duplicate_detector.detected_duplicates
            ),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to run duplicate analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to run duplicate analysis")


@router.get("/trends")
async def get_deduplication_trends(
    hours: int = Query(24, ge=1, le=720)
) -> Dict[str, Any]:
    """
    Get deduplication trends over time.
    
    Args:
        hours: Number of hours to analyze (1-720)
    
    Returns:
        Trend analysis and patterns
    """
    try:
        from datetime import timedelta
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_duplicates = [
            d for d in duplicate_detector.detected_duplicates
            if d.detected_at > cutoff_time
        ]
        
        # Analyze trends
        source_pair_counts: Dict[str, int] = {}
        similarity_buckets = {'exact': 0, 'high': 0, 'medium': 0, 'low': 0}
        
        for dup in recent_duplicates:
            # Count by source pair
            key = f"{dup.source1}↔{dup.source2}"
            source_pair_counts[key] = source_pair_counts.get(key, 0) + 1
            
            # Categorize by similarity
            if dup.similarity_score == 1.0:
                similarity_buckets['exact'] += 1
            elif dup.similarity_score >= 0.95:
                similarity_buckets['high'] += 1
            elif dup.similarity_score >= 0.85:
                similarity_buckets['medium'] += 1
            else:
                similarity_buckets['low'] += 1
        
        return {
            "period_hours": hours,
            "duplicates_detected": len(recent_duplicates),
            "duplicates_by_source_pair": source_pair_counts,
            "duplicates_by_similarity": similarity_buckets,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get deduplication trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to get deduplication trends")


@router.post("/recommendations")
async def get_recommendations() -> Dict[str, Any]:
    """
    Get recommendations for improving data quality.
    
    Based on duplicate detection history, suggests improvements
    to reduce duplicates and improve data quality.
    
    Returns:
        - key_issues: Main issues identified
        - recommendations: Suggested improvements
        - priority: Overall priority
    """
    try:
        stats = duplicate_detector.get_statistics()
        duplicates = duplicate_detector.detected_duplicates
        
        recommendations = dedup_analyzer.get_deduplication_recommendations(
            stats,
            duplicates
        )
        
        # Determine priority
        priority = "low"
        if stats.get('deduplication_rate_percent', 0) > 20:
            priority = "critical"
        elif stats.get('deduplication_rate_percent', 0) > 10:
            priority = "high"
        elif stats.get('deduplication_rate_percent', 0) > 5:
            priority = "medium"
        
        return {
            "summary": stats,
            "recommendations": recommendations,
            "overall_priority": priority,
            "next_steps": [
                "1. Review recommendations above",
                "2. Implement suggested changes",
                "3. Re-run analysis to measure improvement",
                "4. Monitor duplicates over time"
            ],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recommendations")


@router.post("/clear-history")
async def clear_duplicate_history() -> Dict[str, str]:
    """
    Clear duplicate detection history.
    
    ⚠️ Warning: This will delete all duplicate records!
    """
    try:
        count = len(duplicate_detector.detected_duplicates)
        duplicate_detector.clear_history()
        
        logger.warning(f"Duplicate detection history cleared ({count} records deleted)")
        
        return {
            "status": "success",
            "message": f"Cleared {count} duplicate records",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to clear duplicate history: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear duplicate history")


@router.get("/compare/{item1_id}/{item2_id}")
async def compare_items(
    item1_id: str,
    item2_id: str
) -> Dict[str, Any]:
    """
    Compare two specific items for duplication.
    
    Args:
        item1_id: First item ID
        item2_id: Second item ID
    
    Returns:
        Detailed comparison
    """
    try:
        # Find matching duplicate record
        match = next(
            (d for d in duplicate_detector.detected_duplicates
             if (d.item1_id == item1_id and d.item2_id == item2_id) or
                (d.item1_id == item2_id and d.item2_id == item1_id)),
            None
        )
        
        if not match:
            raise HTTPException(
                status_code=404,
                detail=f"No duplicate match found for items {item1_id} and {item2_id}"
            )
        
        return {
            "comparison": match.to_dict(),
            "matched_fields": match.matched_fields,
            "is_exact_match": match.similarity_score == 1.0,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compare items: {e}")
        raise HTTPException(status_code=500, detail="Failed to compare items")
