"""
Istio proxy management and analysis tools
"""
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
import subprocess

from ..base import AsyncTool, ToolResult, ToolParameter, ToolCategory

logger = logging.getLogger(__name__)

class ProxyTool(AsyncTool):
    """Tool for Istio proxy status and configuration analysis"""
    
    def __init__(self, istio_namespace: str = "istio-system"):
        super().__init__(
            name="istio_proxy",
            description="Analyze Istio proxy status, configuration, and health",
            category=ToolCategory.ISTIO
        )
        self.istio_namespace = istio_namespace
    
    async def execute(self, action: str, **kwargs) -> ToolResult:
        """Execute Istio proxy commands"""
        try:
            if action == "status":
                return await self._get_proxy_status(**kwargs)
            elif action == "config":
                return await self._get_proxy_config(**kwargs)
            elif action == "clusters":
                return await self._get_proxy_clusters(**kwargs)
            elif action == "listeners":
                return await self._get_proxy_listeners(**kwargs)
            elif action == "stats":
                return await self._get_proxy_stats(**kwargs)
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown action: {action}. Available: status, config, clusters, listeners, stats"
                )
        except Exception as e:
            logger.error(f"Error in proxy tool: {e}")
            return ToolResult(success=False, error=str(e))
    
    async def _get_proxy_status(self, **kwargs) -> ToolResult:
        """Get Istio proxy status using istioctl"""
        try:
            # Run istioctl proxy-status
            cmd = ["istioctl", "proxy-status"]
            
            # Add namespace filter if specified
            namespace = kwargs.get("namespace")
            if namespace:
                cmd.extend(["-n", namespace])
            
            result = await self._run_istioctl_command(cmd)
            
            if result["success"]:
                # Parse and analyze the output
                analysis = self._analyze_proxy_status(result["output"])
                
                return ToolResult(
                    success=True,
                    data={
                        "raw_output": result["output"],
                        "analysis": analysis
                    },
                    metadata={"command": " ".join(cmd)}
                )
            else:
                return ToolResult(
                    success=False,
                    error=result["error"],
                    data=result["output"]
                )
        
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get proxy status: {e}")
    
    async def _get_proxy_config(self, pod_name: str, namespace: str = "default", **kwargs) -> ToolResult:
        """Get proxy configuration for a specific pod"""
        try:
            config_type = kwargs.get("config_type", "dump")
            
            if config_type == "dump":
                cmd = ["istioctl", "proxy-config", "all", f"{pod_name}.{namespace}"]
            else:
                cmd = ["istioctl", "proxy-config", config_type, f"{pod_name}.{namespace}"]
            
            # Add output format
            output_format = kwargs.get("format", "json")
            if output_format in ["json", "yaml"]:
                cmd.extend(["-o", output_format])
            
            result = await self._run_istioctl_command(cmd)
            
            if result["success"]:
                # Try to parse as JSON if format is json
                parsed_data = result["output"]
                if output_format == "json":
                    try:
                        parsed_data = json.loads(result["output"])
                    except json.JSONDecodeError:
                        pass  # Keep as string if not valid JSON
                
                return ToolResult(
                    success=True,
                    data=parsed_data,
                    metadata={
                        "pod": pod_name,
                        "namespace": namespace,
                        "config_type": config_type,
                        "format": output_format
                    }
                )
            else:
                return ToolResult(success=False, error=result["error"])
        
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get proxy config: {e}")
    
    async def _get_proxy_clusters(self, pod_name: str, namespace: str = "default", **kwargs) -> ToolResult:
        """Get cluster configuration for a proxy"""
        try:
            cmd = ["istioctl", "proxy-config", "cluster", f"{pod_name}.{namespace}"]
            
            # Add filters if specified
            fqdn = kwargs.get("fqdn")
            if fqdn:
                cmd.extend(["--fqdn", fqdn])
            
            cmd.extend(["-o", "json"])
            
            result = await self._run_istioctl_command(cmd)
            
            if result["success"]:
                try:
                    clusters = json.loads(result["output"])
                    analysis = self._analyze_clusters(clusters)
                    
                    return ToolResult(
                        success=True,
                        data={
                            "clusters": clusters,
                            "analysis": analysis
                        },
                        metadata={"pod": pod_name, "namespace": namespace}
                    )
                except json.JSONDecodeError:
                    return ToolResult(
                        success=True,
                        data=result["output"],
                        metadata={"pod": pod_name, "namespace": namespace}
                    )
            else:
                return ToolResult(success=False, error=result["error"])
        
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get clusters: {e}")
    
    async def _get_proxy_listeners(self, pod_name: str, namespace: str = "default", **kwargs) -> ToolResult:
        """Get listener configuration for a proxy"""
        try:
            cmd = ["istioctl", "proxy-config", "listener", f"{pod_name}.{namespace}", "-o", "json"]
            
            result = await self._run_istioctl_command(cmd)
            
            if result["success"]:
                try:
                    listeners = json.loads(result["output"])
                    analysis = self._analyze_listeners(listeners)
                    
                    return ToolResult(
                        success=True,
                        data={
                            "listeners": listeners,
                            "analysis": analysis
                        },
                        metadata={"pod": pod_name, "namespace": namespace}
                    )
                except json.JSONDecodeError:
                    return ToolResult(success=True, data=result["output"])
            else:
                return ToolResult(success=False, error=result["error"])
        
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get listeners: {e}")
    
    async def _get_proxy_stats(self, pod_name: str, namespace: str = "default", **kwargs) -> ToolResult:
        """Get proxy statistics"""
        try:
            # Get stats via kubectl port-forward to Envoy admin interface
            # This is more complex and may require additional setup
            
            # For now, return a simplified version
            return ToolResult(
                success=True,
                data="Proxy stats retrieval not yet implemented. Use 'kubectl port-forward' to access Envoy admin interface.",
                metadata={"pod": pod_name, "namespace": namespace}
            )
        
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get stats: {e}")
    
    async def _run_istioctl_command(self, cmd: List[str]) -> Dict[str, Any]:
        """Run istioctl command and return result"""
        try:
            logger.debug(f"Running command: {' '.join(cmd)}")
            
            # Check if istioctl is available
            try:
                subprocess.run(["istioctl", "version", "--short"], 
                             capture_output=True, check=True, timeout=10)
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                return {
                    "success": False,
                    "error": "istioctl not found or not accessible. Ensure Istio is installed and istioctl is in PATH.",
                    "output": ""
                }
            
            # Run the actual command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
            
            if process.returncode == 0:
                return {
                    "success": True,
                    "output": stdout.decode().strip(),
                    "error": ""
                }
            else:
                return {
                    "success": False,
                    "output": stdout.decode().strip(),
                    "error": stderr.decode().strip()
                }
        
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Command timed out",
                "output": ""
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": ""
            }
    
    def _analyze_proxy_status(self, status_output: str) -> Dict[str, Any]:
        """Analyze proxy status output"""
        analysis = {
            "total_proxies": 0,
            "synced_proxies": 0,
            "stale_proxies": [],
            "issues": []
        }
        
        lines = status_output.split('\n')
        for line in lines[1:]:  # Skip header
            if line.strip():
                parts = line.split()
                if len(parts) >= 5:
                    proxy_name = parts[0]
                    cds, lds, eds, rds = parts[1:5]
                    
                    analysis["total_proxies"] += 1
                    
                    if all(status == "SYNCED" for status in [cds, lds, eds, rds]):
                        analysis["synced_proxies"] += 1
                    else:
                        stale_configs = []
                        if cds != "SYNCED":
                            stale_configs.append("CDS")
                        if lds != "SYNCED":
                            stale_configs.append("LDS")
                        if eds != "SYNCED":
                            stale_configs.append("EDS")
                        if rds != "SYNCED":
                            stale_configs.append("RDS")
                        
                        analysis["stale_proxies"].append({
                            "proxy": proxy_name,
                            "stale_configs": stale_configs
                        })
                        
                        analysis["issues"].append(
                            f"Proxy {proxy_name} has stale {', '.join(stale_configs)} configuration"
                        )
        
        return analysis
    
    def _analyze_clusters(self, clusters: List[Dict]) -> Dict[str, Any]:
        """Analyze cluster configuration"""
        analysis = {
            "total_clusters": len(clusters),
            "healthy_clusters": 0,
            "unhealthy_clusters": [],
            "cluster_types": {}
        }
        
        for cluster in clusters:
            cluster_name = cluster.get("name", "unknown")
            
            # Count cluster types
            cluster_type = cluster.get("type", "unknown")
            analysis["cluster_types"][cluster_type] = analysis["cluster_types"].get(cluster_type, 0) + 1
            
            # Check health (simplified)
            endpoints = cluster.get("endpoints", [])
            if endpoints:
                analysis["healthy_clusters"] += 1
            else:
                analysis["unhealthy_clusters"].append(cluster_name)
        
        return analysis
    
    def _analyze_listeners(self, listeners: List[Dict]) -> Dict[str, Any]:
        """Analyze listener configuration"""
        analysis = {
            "total_listeners": len(listeners),
            "inbound_listeners": 0,
            "outbound_listeners": 0,
            "ports": []
        }
        
        for listener in listeners:
            address = listener.get("address", {})
            port = address.get("socketAddress", {}).get("portValue", 0)
            
            if port:
                analysis["ports"].append(port)
            
            # Determine if inbound or outbound (simplified heuristic)
            name = listener.get("name", "").lower()
            if "inbound" in name or port in [15006, 15001]:
                analysis["inbound_listeners"] += 1
            else:
                analysis["outbound_listeners"] += 1
        
        return analysis
    
    def get_parameters(self) -> List[ToolParameter]:
        """Get tool parameters"""
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform",
                required=True,
                enum_values=["status", "config", "clusters", "listeners", "stats"]
            ),
            ToolParameter(
                name="pod_name",
                type="string",
                description="Pod name for proxy-specific operations",
                required=False
            ),
            ToolParameter(
                name="namespace",
                type="string",
                description="Kubernetes namespace",
                required=False,
                default="default"
            ),
            ToolParameter(
                name="config_type",
                type="string",
                description="Type of config to retrieve (for config action)",
                required=False,
                enum_values=["dump", "cluster", "listener", "route", "endpoint"],
                default="dump"
            ),
            ToolParameter(
                name="format",
                type="string",
                description="Output format",
                required=False,
                enum_values=["json", "yaml", "table"],
                default="json"
            )
        ]
