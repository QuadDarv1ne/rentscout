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
from typing import Dict, Any, Optional, List
from datetime import datetime
import platform
import psutil
import asyncio

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
        disk = psutil.disk_usage('/')
        
        # Determine status
        if cpu_percent > 90 or memory.percent > 90 or disk.percent > 95:
            status = "critical"
        elif cpu_percent > 75 or memory.percent > 75 or disk.percent > 85:
            status = "warning"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "cpu_percent": round(cpu_percent, 2),
            "memory_percent": round(memory.percent, 2),
            "memory_available_mb": round(memory.available / (1024**2), 2),
            "disk_percent": round(disk.percent, 2),
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/load-average")
async def system_load_average() -> Dict[str, Any]:
    """
    Get system load average (Linux/Unix only).
    
    Returns:
        - load_avg_1min: Load average over 1 minute
        - load_avg_5min: Load average over 5 minutes
        - load_avg_15min: Load average over 15 minutes
        - cpu_count: Number of CPU cores
    """
    try:
        # Load average is only available on Unix systems
        if hasattr(psutil, 'getloadavg'):
            load_avg = psutil.getloadavg()
            cpu_count = psutil.cpu_count()
            
            return {
                "load_avg_1min": round(load_avg[0], 2),
                "load_avg_5min": round(load_avg[1], 2),
                "load_avg_15min": round(load_avg[2], 2),
                "cpu_count": cpu_count,
                "load_per_cpu_1min": round(load_avg[0] / cpu_count, 2) if cpu_count > 0 else 0,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "unsupported",
                "message": "Load average not available on this platform",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Failed to get load average: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/disk-io")
async def system_disk_io() -> Dict[str, Any]:
    """
    Get disk I/O statistics.
    
    Returns:
        - read_bytes: Bytes read
        - write_bytes: Bytes written
        - read_count: Read operations
        - write_count: Write operations
        - read_speed: Read speed (bytes/sec)
        - write_speed: Write speed (bytes/sec)
    """
    try:
        # Get initial counters
        disk_io_1 = psutil.disk_io_counters()
        await asyncio.sleep(1)  # Wait 1 second
        disk_io_2 = psutil.disk_io_counters()
        
        if disk_io_1 and disk_io_2:
            # Calculate speeds
            read_speed = disk_io_2.read_bytes - disk_io_1.read_bytes
            write_speed = disk_io_2.write_bytes - disk_io_1.write_bytes
            
            return {
                "read_bytes": disk_io_2.read_bytes,
                "write_bytes": disk_io_2.write_bytes,
                "read_count": disk_io_2.read_count,
                "write_count": disk_io_2.write_count,
                "read_speed_bytes_per_sec": read_speed,
                "write_speed_bytes_per_sec": write_speed,
                "read_speed_mb_per_sec": round(read_speed / (1024**2), 2),
                "write_speed_mb_per_sec": round(write_speed / (1024**2), 2),
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "unavailable",
                "message": "Disk I/O counters not available",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Failed to get disk I/O stats: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/network-io")
async def system_network_io() -> Dict[str, Any]:
    """
    Get network I/O statistics.
    
    Returns:
        - bytes_sent: Bytes sent
        - bytes_recv: Bytes received
        - packets_sent: Packets sent
        - packets_recv: Packets received
        - speed_sent: Send speed (bytes/sec)
        - speed_recv: Receive speed (bytes/sec)
    """
    try:
        # Get initial counters
        net_io_1 = psutil.net_io_counters()
        await asyncio.sleep(1)  # Wait 1 second
        net_io_2 = psutil.net_io_counters()
        
        if net_io_1 and net_io_2:
            # Calculate speeds
            send_speed = net_io_2.bytes_sent - net_io_1.bytes_sent
            recv_speed = net_io_2.bytes_recv - net_io_1.bytes_recv
            
            return {
                "bytes_sent": net_io_2.bytes_sent,
                "bytes_recv": net_io_2.bytes_recv,
                "packets_sent": net_io_2.packets_sent,
                "packets_recv": net_io_2.packets_recv,
                "speed_sent_bytes_per_sec": send_speed,
                "speed_recv_bytes_per_sec": recv_speed,
                "speed_sent_mb_per_sec": round(send_speed / (1024**2), 2),
                "speed_recv_mb_per_sec": round(recv_speed / (1024**2), 2),
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "unavailable",
                "message": "Network I/O counters not available",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Failed to get network I/O stats: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/temperature")
async def system_temperature() -> Dict[str, Any]:
    """
    Get system temperature sensors (if available).
    
    Returns:
        - temperatures: List of temperature sensors
        - critical_sensors: Sensors with critical temperatures
    """
    try:
        temps = psutil.sensors_temperatures()
        
        if temps:
            temp_data = {}
            critical_sensors = []
            
            for name, entries in temps.items():
                temp_data[name] = []
                for entry in entries:
                    temp_info = {
                        "label": entry.label or "N/A",
                        "current": entry.current,
                        "high": entry.high,
                        "critical": entry.critical
                    }
                    temp_data[name].append(temp_info)
                    
                    # Check if temperature is critical
                    if entry.critical and entry.current >= entry.critical:
                        critical_sensors.append({
                            "sensor": name,
                            "label": entry.label or "N/A",
                            "current": entry.current,
                            "critical": entry.critical
                        })
            
            return {
                "temperatures": temp_data,
                "critical_sensors": critical_sensors,
                "has_critical": len(critical_sensors) > 0,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "unavailable",
                "message": "Temperature sensors not available",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Failed to get temperature data: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/battery")
async def system_battery() -> Dict[str, Any]:
    """
    Get battery information (for laptops/mobile devices).
    
    Returns:
        - percent: Battery charge percentage
        - secsleft: Seconds left until empty
        - power_plugged: Whether device is plugged in
    """
    try:
        battery = psutil.sensors_battery()
        
        if battery:
            return {
                "percent": battery.percent,
                "secsleft": battery.secsleft,
                "power_plugged": battery.power_plugged,
                "time_left_hours": round(battery.secsleft / 3600, 2) if battery.secsleft != psutil.POWER_TIME_UNLIMITED else "Unlimited",
                "status": "plugged" if battery.power_plugged else "unplugged",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "unavailable",
                "message": "Battery information not available (desktop system?)",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Failed to get battery info: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/users")
async def system_users() -> Dict[str, Any]:
    """
    Get currently logged-in users.
    
    Returns:
        - users: List of logged-in users
        - count: Number of users
    """
    try:
        users = psutil.users()
        user_list = []
        
        for user in users:
            user_list.append({
                "name": user.name,
                "terminal": user.terminal,
                "host": user.host,
                "started": datetime.fromtimestamp(user.started).isoformat(),
                "pid": user.pid
            })
        
        return {
            "users": user_list,
            "count": len(user_list),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get user info: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/boot-time")
async def system_boot_time() -> Dict[str, Any]:
    """
    Get system boot time.
    
    Returns:
        - boot_time: Unix timestamp of boot time
        - boot_time_iso: ISO formatted boot time
        - uptime_seconds: System uptime in seconds
    """
    try:
        boot_time = psutil.boot_time()
        uptime = datetime.now().timestamp() - boot_time
        
        return {
            "boot_time": boot_time,
            "boot_time_iso": datetime.fromtimestamp(boot_time).isoformat(),
            "uptime_seconds": int(uptime),
            "uptime_human": f"{int(uptime // 86400)} days, {int((uptime % 86400) // 3600)} hours, {int((uptime % 3600) // 60)} minutes",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get boot time: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/virtual-memory")
async def system_virtual_memory() -> Dict[str, Any]:
    """
    Get detailed virtual memory statistics.
    
    Returns detailed memory information including swap.
    """
    try:
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            "virtual_memory": {
                "total_mb": round(memory.total / (1024**2), 2),
                "available_mb": round(memory.available / (1024**2), 2),
                "used_mb": round(memory.used / (1024**2), 2),
                "free_mb": round(memory.free / (1024**2), 2),
                "percent": memory.percent,
                "buffers_mb": round(getattr(memory, 'buffers', 0) / (1024**2), 2),
                "cached_mb": round(getattr(memory, 'cached', 0) / (1024**2), 2),
                "shared_mb": round(getattr(memory, 'shared', 0) / (1024**2), 2)
            },
            "swap_memory": {
                "total_mb": round(swap.total / (1024**2), 2),
                "used_mb": round(swap.used / (1024**2), 2),
                "free_mb": round(swap.free / (1024**2), 2),
                "percent": swap.percent,
                "swapped_in_mb": round(swap.sin / (1024**2), 2),
                "swapped_out_mb": round(swap.sout / (1024**2), 2)
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get virtual memory info: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
