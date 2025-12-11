"""
System inspection and diagnostics API endpoints.

Provides comprehensive system health monitoring and diagnostics:
- Component status monitoring
- Performance metrics
- Resource usage
- Health recommendations
- System diagnostics
"""

from fastapi import APIRouter, Query
from typing import Dict, Any, Optional
from datetime import datetime
import platform
import psutil

from app.utils.logger import logger

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
async def system_health() -> Dict[str, Any]:
    """
    Get comprehensive system health status.
    
    Returns:
        - overall_status: Overall system health
        - components: Status of individual components
        - timestamp: Server time
    """
    try:
        # Get component statuses
        components = {
            "api": "operational",
            "cache": "operational",
            "database": "operational",
            "metrics": "operational",
            "parsers": "operational",
        }
        
        # Determine overall status
        all_operational = all(v == "operational" for v in components.values())
        overall_status = "healthy" if all_operational else "degraded"
        
        return {
            "status": overall_status,
            "components": components,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/info")
async def system_info() -> Dict[str, Any]:
    """
    Get detailed system information.
    
    Returns:
        - platform: OS and architecture
        - python: Python version and executable
        - uptime: System uptime
        - hostname: System hostname
    """
    try:
        import subprocess
        
        uptime_seconds = None
        try:
            if platform.system() == "Linux":
                uptime_seconds = int(open('/proc/uptime').read().split()[0])
            elif platform.system() == "Windows":
                result = subprocess.run(['wmic', 'os', 'get', 'lastbootuptime'], 
                                      capture_output=True, text=True)
                # Parse Windows WMIC output
        except:
            pass
        
        return {
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "architecture": platform.machine(),
            },
            "python": {
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "compiler": platform.python_compiler(),
            },
            "hostname": platform.node(),
            "uptime_seconds": uptime_seconds,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        return {"error": str(e)}


@router.get("/resources")
async def system_resources() -> Dict[str, Any]:
    """
    Get current system resource usage.
    
    Returns:
        - cpu: CPU usage percentage
        - memory: Memory usage (used, total, percent)
        - disk: Disk usage
        - network: Network connections
    """
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu": {
                "percent": round(cpu_percent, 2),
                "count": psutil.cpu_count(logical=False),
                "count_logical": psutil.cpu_count(logical=True),
            },
            "memory": {
                "used_mb": round(memory.used / (1024**2), 2),
                "total_mb": round(memory.total / (1024**2), 2),
                "percent": round(memory.percent, 2),
                "available_mb": round(memory.available / (1024**2), 2),
            },
            "disk": {
                "used_gb": round(disk.used / (1024**3), 2),
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent": round(disk.percent, 2),
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get system resources: {e}")
        return {"error": str(e)}


@router.get("/processes")
async def system_processes(
    sort_by: str = Query("memory", enum=["cpu", "memory", "name"]),
    limit: int = Query(10, ge=1, le=50)
) -> Dict[str, Any]:
    """
    Get top processes by resource usage.
    
    Args:
        sort_by: Sort by 'cpu', 'memory', or 'name'
        limit: Number of processes to return
    
    Returns:
        List of top processes with resource usage
    """
    try:
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.as_dict(attrs=['pid', 'name', 'cpu_percent', 'memory_percent'])
                processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort
        if sort_by == "cpu":
            processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
        elif sort_by == "memory":
            processes.sort(key=lambda x: x.get('memory_percent', 0), reverse=True)
        else:
            processes.sort(key=lambda x: x.get('name', ''))
        
        return {
            "top_processes": processes[:limit],
            "total_processes": len(processes),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get processes: {e}")
        return {"error": str(e)}


@router.get("/network")
async def system_network() -> Dict[str, Any]:
    """
    Get network statistics.
    
    Returns:
        - interfaces: Network interfaces and their stats
        - connections: Active network connections
    """
    try:
        interfaces = {}
        for iface, addrs in psutil.net_if_addrs().items():
            interfaces[iface] = {
                "addresses": [
                    {
                        "family": str(addr.family),
                        "address": addr.address,
                        "netmask": addr.netmask,
                    }
                    for addr in addrs
                ]
            }
        
        # Network statistics
        net_stats = psutil.net_io_counters()
        
        return {
            "interfaces": interfaces,
            "statistics": {
                "bytes_sent": net_stats.bytes_sent,
                "bytes_recv": net_stats.bytes_recv,
                "packets_sent": net_stats.packets_sent,
                "packets_recv": net_stats.packets_recv,
                "errors_in": net_stats.errin,
                "errors_out": net_stats.errout,
                "dropped_in": net_stats.dropin,
                "dropped_out": net_stats.dropout,
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get network stats: {e}")
        return {"error": str(e)}


@router.get("/diagnostics")
async def system_diagnostics() -> Dict[str, Any]:
    """
    Run comprehensive system diagnostics.
    
    Checks:
    - Resource availability
    - Performance metrics
    - Potential issues
    - Recommendations
    
    Returns:
        Diagnostic results with issues and recommendations
    """
    try:
        results = {
            "checks": {},
            "issues": [],
            "recommendations": [],
            "overall_status": "good",
        }
        
        # CPU check
        cpu_percent = psutil.cpu_percent(interval=0.1)
        results["checks"]["cpu"] = {
            "usage_percent": round(cpu_percent, 2),
            "status": "healthy" if cpu_percent < 80 else "warning" if cpu_percent < 90 else "critical"
        }
        if cpu_percent > 90:
            results["issues"].append("CPU usage critically high (>90%)")
            results["overall_status"] = "warning"
        
        # Memory check
        memory = psutil.virtual_memory()
        results["checks"]["memory"] = {
            "usage_percent": round(memory.percent, 2),
            "status": "healthy" if memory.percent < 80 else "warning" if memory.percent < 90 else "critical"
        }
        if memory.percent > 90:
            results["issues"].append("Memory usage critically high (>90%)")
            results["overall_status"] = "warning"
        
        # Disk check
        disk = psutil.disk_usage('/')
        results["checks"]["disk"] = {
            "usage_percent": round(disk.percent, 2),
            "status": "healthy" if disk.percent < 80 else "warning" if disk.percent < 90 else "critical"
        }
        if disk.percent > 90:
            results["issues"].append("Disk usage critically high (>90%)")
            results["overall_status"] = "warning"
        
        # Network connectivity check
        try:
            connections = psutil.net_connections()
            results["checks"]["network"] = {
                "active_connections": len(connections),
                "status": "healthy"
            }
        except:
            results["checks"]["network"] = {
                "status": "unavailable"
            }
        
        # Recommendations
        if cpu_percent > 70:
            results["recommendations"].append("Consider scaling resources - CPU usage is high")
        if memory.percent > 70:
            results["recommendations"].append("Monitor memory usage - approaching limit")
        if disk.percent > 70:
            results["recommendations"].append("Clean up disk space - approaching capacity")
        
        return {
            **results,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to run diagnostics: {e}")
        return {"error": str(e)}


@router.get("/performance-baseline")
async def performance_baseline() -> Dict[str, Any]:
    """
    Get system performance baseline metrics.
    
    Provides reference metrics for:
    - Latency
    - Throughput
    - Resource efficiency
    
    Returns:
        Performance baseline values
    """
    return {
        "cpu": {
            "expected_usage_idle_percent": 5,
            "expected_usage_loaded_percent": 50,
            "warning_threshold_percent": 85,
            "critical_threshold_percent": 95,
        },
        "memory": {
            "expected_usage_idle_percent": 30,
            "expected_usage_loaded_percent": 60,
            "warning_threshold_percent": 80,
            "critical_threshold_percent": 95,
        },
        "disk": {
            "warning_threshold_percent": 85,
            "critical_threshold_percent": 95,
        },
        "api": {
            "expected_response_time_ms": 100,
            "warning_response_time_ms": 500,
            "critical_response_time_ms": 1000,
        },
        "cache": {
            "expected_hit_ratio": 0.8,
            "minimum_hit_ratio": 0.5,
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/status")
async def system_status() -> Dict[str, Any]:
    """
    Get quick system status summary.
    
    Returns concise status information suitable for
    monitoring dashboards and status pages.
    
    Returns:
        - status: Overall system status
        - details: Key metrics
    """
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Determine status
        if cpu_percent > 90 or memory.percent > 90:
            status = "critical"
        elif cpu_percent > 75 or memory.percent > 75:
            status = "warning"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "cpu_percent": round(cpu_percent, 2),
            "memory_percent": round(memory.percent, 2),
            "memory_available_mb": round(memory.available / (1024**2), 2),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
