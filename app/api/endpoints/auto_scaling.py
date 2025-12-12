"""
API endpoints for Auto-Scaling Engine

Provides insights and recommendations for automatic resource scaling.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Any
from datetime import datetime
from pydantic import BaseModel

from app.utils.auto_scaling import (
    auto_scaling_engine,
    ScalingMetric,
    recommend_scaling
)

router = APIRouter()


# ==================== Pydantic Models ====================

class ScalingRecommendationResponse(BaseModel):
    """Response model for scaling recommendation"""
    resource_type: str
    action: str
    current_value: float
    recommended_value: float
    reason: str
    metrics_involved: List[str]
    confidence: float
    confidence_percent: str
    estimated_improvement: float
    cost_impact: str
    timestamp: str


class ScalingStatistics(BaseModel):
    """Statistics about scaling"""
    total_recommendations: int
    scale_up_count: int
    scale_down_count: int
    scale_out_count: int
    scale_in_count: int
    average_confidence: float
    estimated_total_improvement: float


class ResourceStatus(BaseModel):
    """Status of a resource"""
    resource_type: str
    current_value: float
    min_value: float
    max_value: float
    utilization_percent: float
    scaling_status: str  # "optimal", "scale_up_needed", "scale_down_recommended"
    last_scale_time: str


class AutoScalingReport(BaseModel):
    """Comprehensive auto-scaling report"""
    report_timestamp: str
    active_recommendations: int
    resources_needing_attention: List[str]
    recommended_actions: List[ScalingRecommendationResponse]
    cost_savings_potential: float
    performance_improvement_potential: float


# ==================== Helper Functions ====================

def _get_confidence_text(confidence: float) -> str:
    """Convert confidence to percentage text"""
    return f"{round(confidence * 100)}%"


# ==================== API Endpoints ====================

@router.get("/api/auto-scaling/recommendations")
async def get_scaling_recommendations() -> Dict:
    """
    Get current scaling recommendations
    
    Analyzes current system metrics and provides recommendations
    for resource scaling.
    """
    try:
        recommendations = recommend_scaling()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "count": len(recommendations),
            "recommendations": [
                ScalingRecommendationResponse(
                    resource_type=rec.resource_type.value,
                    action=rec.action.value,
                    current_value=round(rec.current_value, 2),
                    recommended_value=round(rec.recommended_value, 2),
                    reason=rec.reason,
                    metrics_involved=rec.metrics_involved,
                    confidence=round(rec.confidence, 3),
                    confidence_percent=_get_confidence_text(rec.confidence),
                    estimated_improvement=round(rec.estimated_improvement, 2),
                    cost_impact=rec.cost_impact,
                    timestamp=rec.timestamp.isoformat()
                )
                for rec in recommendations
            ] if recommendations else []
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/auto-scaling/resource/{resource_type}")
async def get_resource_status(resource_type: str) -> ResourceStatus:
    """
    Get status of a specific resource
    
    Args:
        resource_type: Type of resource (cpu, memory, parser_workers, etc.)
    
    Returns:
        Current status and scaling recommendations
    """
    try:
        from app.utils.auto_scaling import ResourceType
        
        # Validate resource type
        try:
            rt = ResourceType[resource_type.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Unknown resource type: {resource_type}")
        
        config = auto_scaling_engine.resource_configs.get(rt)
        if not config:
            raise HTTPException(status_code=404, detail=f"No config for {resource_type}")
        
        # Determine scaling status
        utilization = (config.current_value / config.max_value) * 100
        if utilization >= config.scale_up_threshold:
            scaling_status = "scale_up_needed"
        elif utilization <= config.scale_down_threshold:
            scaling_status = "scale_down_recommended"
        else:
            scaling_status = "optimal"
        
        last_scale = config.last_scale_up_time or config.last_scale_down_time
        
        return ResourceStatus(
            resource_type=resource_type,
            current_value=round(config.current_value, 2),
            min_value=round(config.min_value, 2),
            max_value=round(config.max_value, 2),
            utilization_percent=round(utilization, 2),
            scaling_status=scaling_status,
            last_scale_time=last_scale.isoformat() if last_scale else "never"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/auto-scaling/all-resources")
async def get_all_resources() -> Dict[str, Any]:
    """
    Get status of all resources
    
    Returns current utilization and scaling status for all tracked resources.
    """
    try:
        resources = {}
        
        for resource_type, config in auto_scaling_engine.resource_configs.items():
            utilization = (config.current_value / config.max_value) * 100
            
            if utilization >= config.scale_up_threshold:
                scaling_status = "scale_up_needed"
            elif utilization <= config.scale_down_threshold:
                scaling_status = "scale_down_recommended"
            else:
                scaling_status = "optimal"
            
            resources[resource_type.value] = {
                "current_value": round(config.current_value, 2),
                "min_value": round(config.min_value, 2),
                "max_value": round(config.max_value, 2),
                "utilization_percent": round(utilization, 2),
                "scaling_status": scaling_status,
            }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "resources": resources
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/auto-scaling/record-metric/{metric_type}")
async def record_metric(metric_type: str, value: float = Query(..., description="Metric value")) -> Dict:
    """
    Record a system metric for scaling analysis
    
    Args:
        metric_type: Type of metric (cpu_usage, memory_usage, etc.)
        value: Metric value
    
    Returns:
        Confirmation of recording
    """
    try:
        # Validate metric type
        try:
            mt = ScalingMetric[metric_type.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Unknown metric type: {metric_type}")
        
        auto_scaling_engine.record_metric(mt, value)
        
        return {
            "status": "recorded",
            "metric_type": metric_type,
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/auto-scaling/statistics")
async def get_scaling_statistics() -> ScalingStatistics:
    """
    Get statistics about scaling recommendations
    
    Shows trends and patterns in scaling decisions.
    """
    try:
        stats = auto_scaling_engine.get_scaling_statistics()
        
        return ScalingStatistics(
            total_recommendations=stats['total_recommendations'],
            scale_up_count=stats['scale_up_count'],
            scale_down_count=stats['scale_down_count'],
            scale_out_count=stats['scale_out_count'],
            scale_in_count=stats['scale_in_count'],
            average_confidence=round(stats['average_confidence'], 3) if stats['total_recommendations'] > 0 else 0.0,
            estimated_total_improvement=round(stats['estimated_total_improvement'], 2)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/auto-scaling/recent-actions")
async def get_recent_actions(limit: int = Query(10, ge=1, le=50)) -> Dict:
    """
    Get recent scaling recommendations
    
    Args:
        limit: Number of recent actions to return
    
    Returns:
        List of recent scaling actions
    """
    try:
        recent = auto_scaling_engine.get_recent_recommendations(count=limit)
        
        return {
            "count": len(recent),
            "actions": [
                {
                    "resource_type": rec.resource_type.value,
                    "action": rec.action.value,
                    "confidence": round(rec.confidence, 3),
                    "estimated_improvement": round(rec.estimated_improvement, 2),
                    "reason": rec.reason,
                    "timestamp": rec.timestamp.isoformat()
                }
                for rec in recent
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/auto-scaling/analysis")
async def get_scaling_analysis() -> AutoScalingReport:
    """
    Get comprehensive auto-scaling analysis
    
    Analyzes current state and provides detailed recommendations.
    """
    try:
        recommendations = recommend_scaling()
        
        # Identify resources needing attention
        resources_needing_attention = []
        for rec in recommendations:
            if rec.confidence > 0.7:
                resources_needing_attention.append(f"{rec.resource_type.value}: {rec.action.value}")
        
        # Calculate potential improvements
        cost_savings = 0.0
        performance_improvement = 0.0
        
        for rec in recommendations:
            if rec.action.value.startswith("scale_down") or rec.action.value == "scale_in":
                cost_savings += abs(rec.estimated_improvement)
            else:
                performance_improvement += rec.estimated_improvement
        
        return AutoScalingReport(
            report_timestamp=datetime.now().isoformat(),
            active_recommendations=len(recommendations),
            resources_needing_attention=resources_needing_attention,
            recommended_actions=[
                ScalingRecommendationResponse(
                    resource_type=rec.resource_type.value,
                    action=rec.action.value,
                    current_value=round(rec.current_value, 2),
                    recommended_value=round(rec.recommended_value, 2),
                    reason=rec.reason,
                    metrics_involved=rec.metrics_involved,
                    confidence=round(rec.confidence, 3),
                    confidence_percent=_get_confidence_text(rec.confidence),
                    estimated_improvement=round(rec.estimated_improvement, 2),
                    cost_impact=rec.cost_impact,
                    timestamp=rec.timestamp.isoformat()
                )
                for rec in recommendations
            ],
            cost_savings_potential=round(cost_savings, 2),
            performance_improvement_potential=round(performance_improvement, 2)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/auto-scaling/health")
async def auto_scaling_health() -> Dict:
    """
    Check health of auto-scaling system
    
    Returns status and capacity information.
    """
    stats = auto_scaling_engine.get_scaling_statistics()
    
    return {
        "status": "healthy",
        "system": "auto_scaling_engine",
        "version": "1.0",
        "total_recommendations": stats['total_recommendations'],
        "confidence_score": round(stats['average_confidence'] * 100, 2) if stats['total_recommendations'] > 0 else 0.0,
        "resources_monitored": len(auto_scaling_engine.resource_configs),
        "metrics_tracked": len(ScalingMetric),
        "timestamp": datetime.now().isoformat()
    }
