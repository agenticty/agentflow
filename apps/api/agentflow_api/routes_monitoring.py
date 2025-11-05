# apps/api/agentflow_api/routes_monitoring.py
"""
Monitoring endpoints for rate limiters, circuit breakers, and system health.
Add this router to your main.py: app.include_router(monitoring_router, prefix="/api/monitoring")
"""

from fastapi import APIRouter
from typing import Dict, Any
from .rate_limiter import (
    openai_circuit_breaker,
    workflow_limiter,
    api_limiter
)

router = APIRouter()


@router.get("/health/circuit-breakers")
async def get_circuit_breaker_status() -> Dict[str, Any]:
    """
    Get status of all circuit breakers.
    
    Returns:
        {
            "openai_api": {
                "state": "closed" | "open" | "half_open",
                "failure_count": 0,
                "last_failure": "2025-01-15T10:30:00"
            }
        }
    """
    return {
        "openai_api": openai_circuit_breaker.get_status()
    }


@router.get("/health/limiters")
async def get_limiter_status() -> Dict[str, Any]:
    """
    Get status of all concurrent request limiters.
    
    Returns:
        {
            "workflows": {
                "current": 3,
                "max": 10,
                "available": 7
            },
            "api_requests": {
                "current": 5,
                "max": 20,
                "available": 15
            }
        }
    """
    return {
        "workflows": workflow_limiter.get_status(),
        "api_requests": api_limiter.get_status()
    }


@router.get("/health/system")
async def get_system_health() -> Dict[str, Any]:
    """
    Combined health check for all rate limiting components.
    
    Returns comprehensive status useful for dashboards and alerting.
    """
    cb_status = openai_circuit_breaker.get_status()
    
    # Determine overall health
    health = "healthy"
    issues = []
    
    if cb_status["state"] == "open":
        health = "degraded"
        issues.append("OpenAI circuit breaker is OPEN - API calls failing")
    elif cb_status["state"] == "half_open":
        health = "recovering"
        issues.append("OpenAI circuit breaker is testing recovery")
    
    wf_status = workflow_limiter.get_status()
    if wf_status["available"] == 0:
        health = "at_capacity"
        issues.append("Workflow limiter at max capacity")
    
    return {
        "status": health,
        "issues": issues,
        "circuit_breakers": {
            "openai_api": cb_status
        },
        "limiters": {
            "workflows": wf_status,
            "api_requests": api_limiter.get_status()
        },
        "recommendations": _get_recommendations(cb_status, wf_status)
    }


def _get_recommendations(cb_status: dict, wf_status: dict) -> list[str]:
    """Generate actionable recommendations based on current state."""
    recommendations = []
    
    if cb_status["state"] == "open":
        recommendations.append(
            "OpenAI API is experiencing issues. Wait 60s before retrying."
        )
    
    if cb_status["failure_count"] >= 3 and cb_status["state"] == "closed":
        recommendations.append(
            "OpenAI API is showing increased failures. Monitor closely."
        )
    
    if wf_status["available"] < 3:
        recommendations.append(
            "Near workflow capacity. Consider scaling or reducing load."
        )
    
    if not recommendations:
        recommendations.append("All systems operating normally.")
    
    return recommendations


@router.post("/admin/circuit-breaker/reset")
async def reset_circuit_breaker(breaker_name: str = "openai_api") -> Dict[str, Any]:
    """
    Manually reset a circuit breaker (admin only - add auth in production).
    
    Useful for clearing a stuck circuit breaker after fixing the underlying issue.
    """
    if breaker_name == "openai_api":
        async with openai_circuit_breaker._lock:
            openai_circuit_breaker.state.state = "closed"
            openai_circuit_breaker.state.failure_count = 0
            openai_circuit_breaker.state.success_count = 0
            openai_circuit_breaker.state.last_failure_time = None
        
        return {
            "success": True,
            "message": f"Circuit breaker '{breaker_name}' reset to CLOSED",
            "status": openai_circuit_breaker.get_status()
        }
    
    return {
        "success": False,
        "message": f"Unknown circuit breaker: {breaker_name}"
    }
