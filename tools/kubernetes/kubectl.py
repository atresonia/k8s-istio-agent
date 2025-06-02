"""
Kubectl tool for executing safe Kubernetes commands
"""
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from ..base import AsyncTool, ToolResult, ToolParameter, ToolCategory

logger = logging.getLogger(__name__)

class KubectlTool(AsyncTool):
    """Tool for executing safe kubectl commands"""
    
    def __init__(self, kubeconfig_file: Optional[str] = None, context: Optional[str] = None):
        super().__init__(
            name="kubectl",
            description="Execute safe kubectl commands to inspect Kubernetes cluster state",
            category=ToolCategory.KUBERNETES
        )
        
        self.safe_commands = [
            "get", "describe", "logs", "top", "explain", "version", 
            "api-resources", "api-versions", "cluster-info"
        ]
        
        # Initialize Kubernetes client
        try:
            if kubeconfig_file:
                config.load_kube_config(config_file=kubeconfig_file, context=context)
            else:
                try:
                    config.load_incluster_config()
                except:
                    config.load_kube_config(context=context)
            
            self.v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            self.api_client = client.ApiClient()
            
            logger.info("Kubernetes client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")
            self.v1 = None
            self.apps_v1 = None
            self.api_client = None
    
    async def execute(self, command: str, namespace: str = "default", **kwargs) -> ToolResult:
        """Execute kubectl command"""
        if not self.v1:
            return ToolResult(
                success=False,
                error="Kubernetes client not initialized. Check kubeconfig.",
                data=None
            )
        
        try:
            # Parse and validate command
            cmd_parts = command.strip().split()
            if not cmd_parts:
                return ToolResult(
                    success=False,
                    error="Empty command provided",
                    data=None
                )
            
            main_cmd = cmd_parts[0].lower()
            if main_cmd not in self.safe_commands:
                return ToolResult(
                    success=False,
                    error=f"Command '{main_cmd}' not allowed. Safe commands: {', '.join(self.safe_commands)}",
                    data=None
                )
            
            # Execute command based on type
            if main_cmd == "get":
                result = await self._handle_get_command(cmd_parts[1:], namespace)
            elif main_cmd == "describe":
                result = await self._handle_describe_command(cmd_parts[1:], namespace)
            elif main_cmd == "logs":
                result = await self._handle_logs_command(cmd_parts[1:], namespace)
            elif main_cmd == "version":
                result = await self._handle_version_command()
            elif main_cmd == "cluster-info":
                result = await self._handle_cluster_info_command()
            else:
                result = f"Command '{main_cmd}' recognized but not yet implemented"
            
            return ToolResult(
                success=True,
                data=result,
                metadata={"command": command, "namespace": namespace}
            )
            
        except Exception as e:
            logger.error(f"Error executing kubectl command: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                data=None
            )
    
    async def _handle_get_command(self, args: List[str], namespace: str) -> str:
        """Handle kubectl get commands"""
        if not args:
            return "Usage: get <resource> [name]"
        
        resource_type = args[0].lower()
        resource_name = args[1] if len(args) > 1 else None
        
        try:
            if resource_type in ["pod", "pods"]:
                return await self._get_pods(namespace, resource_name)
            elif resource_type in ["service", "services", "svc"]:
                return await self._get_services(namespace, resource_name)
            elif resource_type in ["deployment", "deployments", "deploy"]:
                return await self._get_deployments(namespace, resource_name)
            elif resource_type in ["node", "nodes"]:
                return await self._get_nodes(resource_name)
            elif resource_type in ["namespace", "namespaces", "ns"]:
                return await self._get_namespaces(resource_name)
            else:
                return f"Resource type '{resource_type}' not supported yet"
                
        except ApiException as e:
            return f"Kubernetes API error: {e.reason}"
    
    async def _get_pods(self, namespace: str, pod_name: Optional[str] = None) -> str:
        """Get pod information"""
        try:
            if pod_name:
                pod = self.v1.read_namespaced_pod(name=pod_name, namespace=namespace)
                return self._format_pod_detail(pod)
            else:
                pods = self.v1.list_namespaced_pod(namespace=namespace)
                return self._format_pods_list(pods.items)
        except ApiException as e:
            return f"Error getting pods: {e.reason}"
    
    async def _get_services(self, namespace: str, service_name: Optional[str] = None) -> str:
        """Get service information"""
        try:
            if service_name:
                svc = self.v1.read_namespaced_service(name=service_name, namespace=namespace)
                return self._format_service_detail(svc)
            else:
                services = self.v1.list_namespaced_service(namespace=namespace)
                return self._format_services_list(services.items)
        except ApiException as e:
            return f"Error getting services: {e.reason}"
    
    async def _get_deployments(self, namespace: str, deployment_name: Optional[str] = None) -> str:
        """Get deployment information"""
        try:
            if deployment_name:
                deploy = self.apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
                return self._format_deployment_detail(deploy)
            else:
                deployments = self.apps_v1.list_namespaced_deployment(namespace=namespace)
                return self._format_deployments_list(deployments.items)
        except ApiException as e:
            return f"Error getting deployments: {e.reason}"
    
    async def _get_nodes(self, node_name: Optional[str] = None) -> str:
        """Get node information"""
        try:
            if node_name:
                node = self.v1.read_node(name=node_name)
                return self._format_node_detail(node)
            else:
                nodes = self.v1.list_node()
                return self._format_nodes_list(nodes.items)
        except ApiException as e:
            return f"Error getting nodes: {e.reason}"
    
    async def _get_namespaces(self, namespace_name: Optional[str] = None) -> str:
        """Get namespace information"""
        try:
            if namespace_name:
                ns = self.v1.read_namespace(name=namespace_name)
                return self._format_namespace_detail(ns)
            else:
                namespaces = self.v1.list_namespace()
                return self._format_namespaces_list(namespaces.items)
        except ApiException as e:
            return f"Error getting namespaces: {e.reason}"
    
    def _format_pods_list(self, pods) -> str:
        """Format pods list output"""
        if not pods:
            return "No pods found"
        
        output = ["NAME                           READY   STATUS    RESTARTS   AGE"]
        for pod in pods:
            ready_count = sum(1 for c in pod.status.container_statuses or [] if c.ready)
            total_count = len(pod.spec.containers)
            restart_count = sum(c.restart_count for c in pod.status.container_statuses or [])
            
            age = self._calculate_age(pod.metadata.creation_timestamp)
            
            output.append(
                f"{pod.metadata.name:<30} {ready_count}/{total_count:<6} "
                f"{pod.status.phase:<9} {restart_count:<10} {age}"
            )
        
        return "\n".join(output)
    
    def _format_services_list(self, services) -> str:
        """Format services list output"""
        if not services:
            return "No services found"
        
        output = ["NAME         TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE"]
        for svc in services:
            external_ip = svc.status.load_balancer.ingress[0].ip if (
                svc.status.load_balancer and svc.status.load_balancer.ingress
            ) else "<none>"
            
            ports = ",".join([f"{p.port}/{p.protocol}" for p in svc.spec.ports or []])
            age = self._calculate_age(svc.metadata.creation_timestamp)
            
            output.append(
                f"{svc.metadata.name:<12} {svc.spec.type:<11} "
                f"{svc.spec.cluster_ip:<15} {external_ip:<13} {ports:<10} {age}"
            )
        
        return "\n".join(output)
    
    def _calculate_age(self, creation_timestamp) -> str:
        """Calculate age of resource"""
        from datetime import datetime, timezone
        
        if not creation_timestamp:
            return "unknown"
        
        now = datetime.now(timezone.utc)
        age = now - creation_timestamp
        
        if age.days > 0:
            return f"{age.days}d"
        elif age.seconds > 3600:
            return f"{age.seconds // 3600}h"
        elif age.seconds > 60:
            return f"{age.seconds // 60}m"
        else:
            return f"{age.seconds}s"
    
    async def _handle_logs_command(self, args: List[str], namespace: str) -> str:
        """Handle kubectl logs commands"""
        if not args:
            return "Usage: logs <pod-name> [container-name]"
        
        pod_name = args[0]
        container_name = args[1] if len(args) > 1 else None
        
        try:
            logs = self.v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container_name,
                tail_lines=100  # Limit to last 100 lines
            )
            return f"Logs for pod {pod_name}:\n{logs}"
        except ApiException as e:
            return f"Error getting logs: {e.reason}"
    
    async def _handle_version_command(self) -> str:
        """Handle kubectl version command"""
        try:
            version = self.v1.api_client.call_api(
                '/version', 'GET', response_type='object'
            )
            return f"Kubernetes version: {version[0]}"
        except Exception as e:
            return f"Error getting version: {e}"
    
    async def _handle_cluster_info_command(self) -> str:
        """Handle kubectl cluster-info command"""
        try:
            # This is a simplified version
            return "Cluster info: Use 'get nodes' for node information"
        except Exception as e:
            return f"Error getting cluster info: {e}"
    
    def get_parameters(self) -> List[ToolParameter]:
        """Get tool parameters"""
        return [
            ToolParameter(
                name="command",
                type="string",
                description=f"kubectl command to execute. Allowed: {', '.join(self.safe_commands)}",
                required=True
            ),
            ToolParameter(
                name="namespace",
                type="string",
                description="Kubernetes namespace for namespaced resources",
                required=False,
                default="default"
            )
        ]