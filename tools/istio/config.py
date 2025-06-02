"""
Istio configuration analysis and validation tools
"""
import asyncio
import json
import yaml
import logging
from typing import List, Dict, Any, Optional
from kubernetes import client

from ..base import AsyncTool, ToolResult, ToolParameter, ToolCategory

logger = logging.getLogger(__name__)

class ConfigTool(AsyncTool):
    """Tool for Istio configuration analysis and validation"""
    
    def __init__(self, istio_namespace: str = "istio-system"):
        super().__init__(
            name="istio_config",
            description="Analyze and validate Istio configuration resources",
            category=ToolCategory.ISTIO
        )
        self.istio_namespace = istio_namespace
        self._init_k8s_client()
    
    def _init_k8s_client(self):
        """Initialize Kubernetes client"""
        try:
            from kubernetes import config
            try:
                config.load_incluster_config()
            except:
                config.load_kube_config()
            
            self.k8s_client = client.ApiClient()
            self.custom_api = client.CustomObjectsApi()
            self.core_api = client.CoreV1Api()
            
        except Exception as e:
            logger.warning(f"Could not initialize Kubernetes client: {e}")
            self.k8s_client = None
            self.custom_api = None
            self.core_api = None
    
    async def execute(self, action: str, **kwargs) -> ToolResult:
        """Execute Istio configuration commands"""
        if not self.custom_api:
            return ToolResult(
                success=False,
                error="Kubernetes client not available"
            )
        
        try:
            if action == "validate":
                return await self._validate_config(**kwargs)
            elif action == "list":
                return await self._list_resources(**kwargs)
            elif action == "analyze":
                return await self._analyze_config(**kwargs)
            elif action == "check_routing":
                return await self._check_routing(**kwargs)
            elif action == "check_security":
                return await self._check_security(**kwargs)
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown action: {action}. Available: validate, list, analyze, check_routing, check_security"
                )
        except Exception as e:
            logger.error(f"Error in config tool: {e}")
            return ToolResult(success=False, error=str(e))
    
    async def _validate_config(self, namespace: str = "default", **kwargs) -> ToolResult:
        """Validate Istio configuration using istioctl"""
        try:
            cmd = ["istioctl", "analyze"]
            
            if namespace != "all":
                cmd.extend(["-n", namespace])
            else:
                cmd.append("--all-namespaces")
            
            # Add output format
            cmd.extend(["-o", "json"])
            
            result = await self._run_istioctl_command(cmd)
            
            if result["success"]:
                try:
                    analysis_result = json.loads(result["output"]) if result["output"] else []
                    
                    summary = {
                        "total_issues": len(analysis_result),
                        "errors": [msg for msg in analysis_result if msg.get("level") == "Error"],
                        "warnings": [msg for msg in analysis_result if msg.get("level") == "Warning"],
                        "info": [msg for msg in analysis_result if msg.get("level") == "Info"]
                    }
                    
                    return ToolResult(
                        success=True,
                        data={
                            "validation_result": analysis_result,
                            "summary": summary
                        },
                        metadata={"namespace": namespace}
                    )
                except json.JSONDecodeError:
                    # If not JSON, return raw output
                    return ToolResult(
                        success=True,
                        data=result["output"] or "No issues found",
                        metadata={"namespace": namespace}
                    )
            else:
                return ToolResult(success=False, error=result["error"])
        
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to validate config: {e}")
    
    async def _list_resources(self, resource_type: str = "all", namespace: str = "default", **kwargs) -> ToolResult:
        """List Istio configuration resources"""
        try:
            resources = {}
            
            istio_resources = {
                "virtualservices": ("networking.istio.io", "v1beta1"),
                "destinationrules": ("networking.istio.io", "v1beta1"),
                "gateways": ("networking.istio.io", "v1beta1"),
                "serviceentries": ("networking.istio.io", "v1beta1"),
                "sidecars": ("networking.istio.io", "v1beta1"),
                "envoyfilters": ("networking.istio.io", "v1alpha3"),
                "authorizationpolicies": ("security.istio.io", "v1beta1"),
                "peerauthentications": ("security.istio.io", "v1beta1"),
                "requestauthentications": ("security.istio.io", "v1beta1")
            }
            
            target_resources = [resource_type] if resource_type != "all" else istio_resources.keys()
            
            for resource in target_resources:
                if resource in istio_resources:
                    group, version = istio_resources[resource]
                    try:
                        if namespace == "all":
                            response = self.custom_api.list_cluster_custom_object(
                                group=group,
                                version=version,
                                plural=resource
                            )
                        else:
                            response = self.custom_api.list_namespaced_custom_object(
                                group=group,
                                version=version,
                                namespace=namespace,
                                plural=resource
                            )
                        
                        resources[resource] = response.get("items", [])
                        
                    except Exception as e:
                        logger.warning(f"Could not list {resource}: {e}")
                        resources[resource] = []
            
            # Summarize results
            summary = {}
            for resource_name, items in resources.items():
                summary[resource_name] = len(items)
            
            return ToolResult(
                success=True,
                data={
                    "resources": resources,
                    "summary": summary
                },
                metadata={"namespace": namespace, "resource_type": resource_type}
            )
        
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to list resources: {e}")
    
    async def _analyze_config(self, namespace: str = "default", **kwargs) -> ToolResult:
        """Analyze Istio configuration for common issues"""
        try:
            # Get all relevant resources
            list_result = await self._list_resources("all", namespace)
            if not list_result.success:
                return list_result
            
            resources = list_result.data["resources"]
            issues = []
            recommendations = []
            
            # Analyze VirtualServices
            vs_issues = self._analyze_virtual_services(resources.get("virtualservices", []))
            issues.extend(vs_issues)
            
            # Analyze DestinationRules
            dr_issues = self._analyze_destination_rules(resources.get("destinationrules", []))
            issues.extend(dr_issues)
            
            # Analyze Gateways
            gw_issues = self._analyze_gateways(resources.get("gateways", []))
            issues.extend(gw_issues)
            
            # Analyze Security Policies
            sec_issues = self._analyze_security_policies(resources)
            issues.extend(sec_issues)
            
            # Generate recommendations
            if not resources.get("destinationrules"):
                recommendations.append("Consider adding DestinationRules for better traffic management")
            
            if not resources.get("authorizationpolicies"):
                recommendations.append("Consider implementing AuthorizationPolicies for better security")
            
            return ToolResult(
                success=True,
                data={
                    "issues": issues,
                    "recommendations": recommendations,
                    "resource_summary": list_result.data["summary"]
                },
                metadata={"namespace": namespace}
            )
        
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to analyze config: {e}")
    
    def _analyze_virtual_services(self, virtual_services: List[Dict]) -> List[str]:
        """Analyze VirtualService configurations"""
        issues = []
        
        for vs in virtual_services:
            name = vs.get("metadata", {}).get("name", "unknown")
            spec = vs.get("spec", {})
            
            # Check for missing hosts
            if not spec.get("hosts"):
                issues.append(f"VirtualService {name}: No hosts specified")
            
            # Check for missing gateways and mesh
            gateways = spec.get("gateways", [])
            if not gateways:
                issues.append(f"VirtualService {name}: No gateways specified")
            
            # Check HTTP routes
            http_routes = spec.get("http", [])
            for i, route in enumerate(http_routes):
                if not route.get("route"):
                    issues.append(f"VirtualService {name}: HTTP route {i} has no destination")
                
                # Check for weight distribution
                routes = route.get("route", [])
                total_weight = sum(r.get("weight", 100) for r in routes)
                if len(routes) > 1 and total_weight != 100:
                    issues.append(f"VirtualService {name}: Route weights don't sum to 100 ({total_weight})")
        
        return issues
    
    def _analyze_destination_rules(self, destination_rules: List[Dict]) -> List[str]:
        """Analyze DestinationRule configurations"""
        issues = []
        
        for dr in destination_rules:
            name = dr.get("metadata", {}).get("name", "unknown")
            spec = dr.get("spec", {})
            
            # Check for missing host
            if not spec.get("host"):
                issues.append(f"DestinationRule {name}: No host specified")
            
            # Check subset configurations
            subsets = spec.get("subsets", [])
            for subset in subsets:
                if not subset.get("name"):
                    issues.append(f"DestinationRule {name}: Subset missing name")
                if not subset.get("labels"):
                    issues.append(f"DestinationRule {name}: Subset {subset.get('name', 'unnamed')} has no labels")
        
        return issues
    
    def _analyze_gateways(self, gateways: List[Dict]) -> List[str]:
        """Analyze Gateway configurations"""
        issues = []
        
        for gw in gateways:
            name = gw.get("metadata", {}).get("name", "unknown")
            spec = gw.get("spec", {})
            
            # Check selector
            if not spec.get("selector"):
                issues.append(f"Gateway {name}: No selector specified")
            
            # Check servers
            servers = spec.get("servers", [])
            if not servers:
                issues.append(f"Gateway {name}: No servers configured")
            
            for i, server in enumerate(servers):
                if not server.get("hosts"):
                    issues.append(f"Gateway {name}: Server {i} has no hosts")
                if not server.get("port"):
                    issues.append(f"Gateway {name}: Server {i} has no port")
        
        return issues
    
    def _analyze_security_policies(self, resources: Dict[str, List]) -> List[str]:
        """Analyze security policy configurations"""
        issues = []
        
        # Check AuthorizationPolicies
        auth_policies = resources.get("authorizationpolicies", [])
        for policy in auth_policies:
            name = policy.get("metadata", {}).get("name", "unknown")
            spec = policy.get("spec", {})
            
            # Check for overly permissive policies
            if not spec.get("rules") and not spec.get("action"):
                issues.append(f"AuthorizationPolicy {name}: No rules specified (potentially allowing all traffic)")
        
        # Check PeerAuthentication
        peer_auths = resources.get("peerauthentications", [])
        for pa in peer_auths:
            name = pa.get("metadata", {}).get("name", "unknown")
            spec = pa.get("spec", {})
            
            mtls = spec.get("mtls", {})
            if mtls.get("mode") == "DISABLE":
                issues.append(f"PeerAuthentication {name}: mTLS is disabled (security risk)")
        
        return issues
    
    async def _check_routing(self, namespace: str = "default", **kwargs) -> ToolResult:
        """Check routing configuration and conflicts"""
        try:
            # This would implement comprehensive routing analysis
            # For now, return a placeholder
            return ToolResult(
                success=True,
                data="Routing configuration check not yet implemented",
                metadata={"namespace": namespace}
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to check routing: {e}")
    
    async def _check_security(self, namespace: str = "default", **kwargs) -> ToolResult:
        """Check security configuration"""
        try:
            # This would implement comprehensive security analysis
            # For now, return a placeholder
            return ToolResult(
                success=True,
                data="Security configuration check not yet implemented",
                metadata={"namespace": namespace}
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to check security: {e}")
    
    async def _run_istioctl_command(self, cmd: List[str]) -> Dict[str, Any]:
        """Run istioctl command"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
            
            return {
                "success": process.returncode == 0,
                "output": stdout.decode().strip(),
                "error": stderr.decode().strip()
            }
        
        except asyncio.TimeoutError:
            return {"success": False, "output": "", "error": "Command timed out"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}
    
    def get_parameters(self) -> List[ToolParameter]:
        """Get tool parameters"""
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform",
                required=True,
                enum_values=["validate", "list", "analyze", "check_routing", "check_security"]
            ),
            ToolParameter(
                name="namespace",
                type="string",
                description="Kubernetes namespace (use 'all' for all namespaces)",
                required=False,
                default="default"
            ),
            ToolParameter(
                name="resource_type",
                type="string",
                description="Type of Istio resource to list",
                required=False,
                enum_values=["all", "virtualservices", "destinationrules", "gateways", "serviceentries", "authorizationpolicies"],
                default="all"
            )
        ]