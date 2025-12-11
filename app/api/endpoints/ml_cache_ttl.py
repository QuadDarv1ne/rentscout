"""
API endpoints for ML-based Cache TTL Prediction

Provides intelligent cache TTL recommendations based on:
- Historical access patterns
- Data change frequency
- Source-specific behaviors
- Machine learning predictions
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.ml.cache_ttl_predictor import (
    cache_ttl_optimizer,
    predict_cache_ttl,
    DataType,
    TTLPrediction,
)

router = APIRouter()


# ==================== Pydantic Models ====================

class TTLPredictionResponse(BaseModel):
    """Response model for TTL prediction"""
    key: str
    predicted_ttl_seconds: int
    predicted_ttl_hours: float
    predicted_ttl_readable: str
    confidence: float
    confidence_percent: str
    reason: str
    factors: Dict[str, float]
    recommended_action: str
    timestamp: str


class CacheAccessRequest(BaseModel):
    """Request to record cache access"""
    key: str
    data_type: str  # DataType enum value
    size_bytes: int = 0
    source: str = "unknown"


class TTLOptimizationResult(BaseModel):
    """Result of TTL optimization"""
    key: str
    old_ttl_seconds: int
    new_ttl_seconds: int
    savings_percent: float
    change_direction: str  # "increased", "decreased", "unchanged"
    prediction: TTLPredictionResponse


class OptimizationStats(BaseModel):
    """Statistics about TTL optimizations"""
    total_optimizations: int
    average_change_seconds: float
    average_change_percent: float
    optimizations_reducing_ttl: int
    optimizations_increasing_ttl: int
    total_time_saved_hours: float
    efficiency_score: float


class OptimizationCandidate(BaseModel):
    """Candidate for TTL optimization"""
    key: str
    current_ttl_seconds: int
    recommended_ttl_seconds: int
    potential_saving_seconds: int
    saving_percent: float
    priority: str  # "high", "medium", "low"


class CacheAnalysisReport(BaseModel):
    """Comprehensive cache analysis report"""
    analysis_timestamp: str
    total_cached_keys: int
    average_access_frequency: float
    most_accessed_keys: List[str]
    least_accessed_keys: List[str]
    optimization_candidates: List[OptimizationCandidate]
    total_potential_savings: int
    recommendations: List[str]


# ==================== Helper Functions ====================

def _format_ttl(seconds: int) -> str:
    """Format TTL in human-readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    elif seconds < 86400:
        return f"{seconds // 3600}h"
    else:
        return f"{seconds // 86400}d"


def _get_confidence_text(confidence: float) -> str:
    """Get text representation of confidence"""
    if confidence >= 0.9:
        return "Очень высокая (90%+)"
    elif confidence >= 0.7:
        return "Высокая (70-90%)"
    elif confidence >= 0.5:
        return "Средняя (50-70%)"
    else:
        return "Низкая (<50%)"


def _prediction_to_response(prediction: TTLPrediction) -> TTLPredictionResponse:
    """Convert internal prediction to API response"""
    return TTLPredictionResponse(
        key=prediction.key,
        predicted_ttl_seconds=prediction.predicted_ttl_seconds,
        predicted_ttl_hours=round(prediction.predicted_ttl_seconds / 3600, 2),
        predicted_ttl_readable=_format_ttl(prediction.predicted_ttl_seconds),
        confidence=round(prediction.confidence, 3),
        confidence_percent=_get_confidence_text(prediction.confidence),
        reason=prediction.reason,
        factors={k: round(v, 3) for k, v in prediction.factors.items()},
        recommended_action=prediction.recommended_action,
        timestamp=datetime.now().isoformat()
    )


# ==================== API Endpoints ====================

@router.post("/api/ml/cache-ttl/predict")
async def predict_ttl_endpoint(request: CacheAccessRequest) -> TTLPredictionResponse:
    """
    Predict optimal cache TTL for a key
    
    Uses ML model trained on historical access patterns to recommend
    optimal time-to-live for cached data.
    
    Args:
        key: Cache key identifier
        data_type: Type of data (property, search_result, etc.)
        size_bytes: Size of cached data in bytes
        source: Data source/parser name
    
    Returns:
        TTLPrediction with recommended TTL and confidence score
    """
    try:
        # Validate data type
        try:
            data_type = DataType[request.data_type.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Unknown data type: {request.data_type}")
        
        # Get prediction
        prediction = predict_cache_ttl(
            key=request.key,
            data_type=data_type,
            current_ttl=3600,  # Default
            size_bytes=request.size_bytes,
            source=request.source.lower()
        )
        
        return _prediction_to_response(prediction)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/ml/cache-ttl/predict/{key}")
async def predict_ttl_for_key(
    key: str,
    data_type: str = Query("property", description="Type of data"),
    size_bytes: int = Query(0, description="Size in bytes"),
    source: str = Query("unknown", description="Data source")
) -> TTLPredictionResponse:
    """
    Predict optimal TTL for a specific cache key
    
    Analyzes historical access patterns and returns ML-based recommendation.
    """
    try:
        try:
            dt = DataType[data_type.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Unknown data type: {data_type}")
        
        prediction = predict_cache_ttl(
            key=key,
            data_type=dt,
            current_ttl=3600,
            size_bytes=size_bytes,
            source=source.lower()
        )
        
        return _prediction_to_response(prediction)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ml/cache-ttl/optimize/{key}")
async def optimize_ttl_endpoint(
    key: str,
    current_ttl: int = Query(..., description="Current TTL in seconds", gt=0)
) -> TTLOptimizationResult:
    """
    Apply ML-based TTL optimization to a cache key
    
    Returns new recommended TTL and optimization details.
    """
    try:
        new_ttl, prediction = cache_ttl_optimizer.apply_ttl_optimization(key, current_ttl)
        
        if current_ttl == new_ttl:
            change_direction = "unchanged"
            savings_percent = 0.0
        elif new_ttl < current_ttl:
            change_direction = "decreased"
            savings_percent = ((current_ttl - new_ttl) / current_ttl) * 100
        else:
            change_direction = "increased"
            savings_percent = ((current_ttl - new_ttl) / current_ttl) * 100
        
        return TTLOptimizationResult(
            key=key,
            old_ttl_seconds=current_ttl,
            new_ttl_seconds=new_ttl,
            savings_percent=round(savings_percent, 2),
            change_direction=change_direction,
            prediction=_prediction_to_response(prediction)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ml/cache-ttl/record-access")
async def record_cache_access(request: CacheAccessRequest) -> Dict:
    """
    Record cache access for ML training data collection
    
    Helps the ML model learn about actual access patterns.
    """
    try:
        try:
            data_type = DataType[request.data_type.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Unknown data type: {request.data_type}")
        
        cache_ttl_optimizer.record_cache_access(
            key=request.key,
            data_type=data_type,
            size_bytes=request.size_bytes,
            source=request.source.lower()
        )
        
        return {
            "status": "recorded",
            "key": request.key,
            "data_type": request.data_type,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/ml/cache-ttl/statistics")
async def get_ttl_statistics() -> OptimizationStats:
    """
    Get statistics about TTL predictions and optimizations
    
    Shows how well the ML model is performing and what kind of
    improvements have been made through predictions.
    """
    try:
        stats = cache_ttl_optimizer.get_optimization_stats()
        
        # Calculate efficiency score
        if stats['total_optimizations'] == 0:
            efficiency_score = 0.0
        else:
            # Higher score = more effective optimizations
            reducing = stats['optimizations_reducing_ttl']
            total = stats['total_optimizations']
            efficiency_score = (reducing / total) * 100
        
        # Calculate total time saved in hours
        total_saved = 0
        for _, _, old_ttl, new_ttl in cache_ttl_optimizer.optimization_history:
            total_saved += (old_ttl - new_ttl)
        
        return OptimizationStats(
            total_optimizations=stats['total_optimizations'],
            average_change_seconds=round(stats['average_change_seconds'], 2),
            average_change_percent=round(stats['average_change_percent'], 2),
            optimizations_reducing_ttl=stats['optimizations_reducing_ttl'],
            optimizations_increasing_ttl=stats['optimizations_increasing_ttl'],
            total_time_saved_hours=round(total_saved / 3600, 2),
            efficiency_score=round(efficiency_score, 2)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/ml/cache-ttl/candidates")
async def get_optimization_candidates(
    top_n: int = Query(10, description="Number of candidates to return", ge=1, le=50)
) -> List[OptimizationCandidate]:
    """
    Get top candidates for TTL optimization
    
    Returns keys that would benefit most from TTL optimization based on
    ML predictions vs current settings.
    """
    try:
        candidates_list = cache_ttl_optimizer.get_top_optimization_candidates(top_n)
        
        candidates = []
        for key, current_ttl, recommended_ttl in candidates_list:
            potential_saving = abs(current_ttl - recommended_ttl)
            
            if recommended_ttl < current_ttl:
                saving_percent = ((current_ttl - recommended_ttl) / current_ttl) * 100
                priority = "high" if saving_percent > 30 else "medium"
            elif recommended_ttl > current_ttl:
                saving_percent = ((current_ttl - recommended_ttl) / current_ttl) * 100
                priority = "low"
            else:
                saving_percent = 0.0
                priority = "low"
            
            candidates.append(OptimizationCandidate(
                key=key,
                current_ttl_seconds=current_ttl,
                recommended_ttl_seconds=recommended_ttl,
                potential_saving_seconds=potential_saving,
                saving_percent=round(abs(saving_percent), 2),
                priority=priority
            ))
        
        return candidates
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/ml/cache-ttl/analysis")
async def get_cache_analysis() -> CacheAnalysisReport:
    """
    Get comprehensive cache analysis report
    
    Analyzes cache patterns and provides recommendations for optimization.
    """
    try:
        patterns = cache_ttl_optimizer.analyzer.patterns
        
        if not patterns:
            return CacheAnalysisReport(
                analysis_timestamp=datetime.now().isoformat(),
                total_cached_keys=0,
                average_access_frequency=0.0,
                most_accessed_keys=[],
                least_accessed_keys=[],
                optimization_candidates=[],
                total_potential_savings=0,
                recommendations=["Нет данных для анализа. Начните использовать систему кеша."]
            )
        
        # Calculate stats
        access_frequencies = [p.access_frequency for p in patterns.values()]
        avg_frequency = sum(access_frequencies) / len(access_frequencies) if access_frequencies else 0.0
        
        # Get most/least accessed
        sorted_patterns = sorted(patterns.items(), key=lambda x: x[1].access_frequency, reverse=True)
        most_accessed = [k for k, _ in sorted_patterns[:5]]
        least_accessed = [k for k, _ in sorted_patterns[-5:]]
        
        # Get candidates
        candidates_list = cache_ttl_optimizer.get_top_optimization_candidates(top_n=5)
        optimization_candidates = []
        total_savings = 0
        
        for key, current_ttl, recommended_ttl in candidates_list:
            potential_saving = abs(current_ttl - recommended_ttl)
            total_savings += potential_saving
            
            saving_percent = ((current_ttl - recommended_ttl) / current_ttl * 100) if current_ttl > 0 else 0
            priority = "high" if abs(saving_percent) > 30 else "medium" if abs(saving_percent) > 10 else "low"
            
            optimization_candidates.append(OptimizationCandidate(
                key=key,
                current_ttl_seconds=current_ttl,
                recommended_ttl_seconds=recommended_ttl,
                potential_saving_seconds=potential_saving,
                saving_percent=round(abs(saving_percent), 2),
                priority=priority
            ))
        
        # Generate recommendations
        recommendations = []
        if avg_frequency < 1.0:
            recommendations.append("💡 Низкая частота доступа - рассмотрите увеличение TTL")
        if len(most_accessed) > 0:
            recommendations.append(f"⚡ Оптимизируйте {len(optimization_candidates)} высокоприоритетных ключей")
        recommendations.append("📊 Используйте /api/ml/cache-ttl/candidates для деталей")
        
        return CacheAnalysisReport(
            analysis_timestamp=datetime.now().isoformat(),
            total_cached_keys=len(patterns),
            average_access_frequency=round(avg_frequency, 3),
            most_accessed_keys=most_accessed,
            least_accessed_keys=least_accessed,
            optimization_candidates=optimization_candidates,
            total_potential_savings=total_savings,
            recommendations=recommendations
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ml/cache-ttl/cleanup")
async def cleanup_ttl_data() -> Dict:
    """
    Cleanup old patterns and optimization history
    
    Removes patterns older than 1 week without recent access to save memory.
    """
    try:
        initial_count = len(cache_ttl_optimizer.analyzer.patterns)
        cache_ttl_optimizer.cleanup()
        final_count = len(cache_ttl_optimizer.analyzer.patterns)
        
        return {
            "status": "cleaned",
            "patterns_removed": initial_count - final_count,
            "remaining_patterns": final_count,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/ml/cache-ttl/health")
async def cache_ttl_health() -> Dict:
    """
    Check health and status of ML cache TTL predictor
    
    Returns information about the ML model state and data collection.
    """
    patterns = cache_ttl_optimizer.analyzer.patterns
    history = cache_ttl_optimizer.optimization_history
    
    return {
        "status": "healthy",
        "model_name": "Cache TTL Predictor v1.0",
        "patterns_collected": len(patterns),
        "optimizations_performed": len(history),
        "average_confidence": round(
            sum(cache_ttl_optimizer.predictor.prediction_accuracy) / len(cache_ttl_optimizer.predictor.prediction_accuracy)
            if cache_ttl_optimizer.predictor.prediction_accuracy else 0,
            3
        ),
        "timestamp": datetime.now().isoformat()
    }
