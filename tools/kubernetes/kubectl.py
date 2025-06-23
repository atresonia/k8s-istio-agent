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
            self.networking_v1 = client.NetworkingV1Api()
            self.api_client = client.ApiClient()
            
            logger.info("Kubernetes client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")
            self.v1 = None
            self.apps_v1 = None
            self.networking_v1 = None
            self.api_client = None
    
    def _extract_namespace_from_command(self, cmd_parts: List[str]) -> tuple[List[str], str]:
        """Extract namespace from command parts and return remaining parts and namespace"""
        namespace = "default"
        remaining_parts = []
        i = 0
        while i < len(cmd_parts):
            if cmd_parts[i] in ["-n", "--namespace"]:
                if i + 1 < len(cmd_parts):
                    namespace = cmd_parts[i + 1]
                    i += 2
                else:
                    i += 1
            else:
                remaining_parts.append(cmd_parts[i])
                i += 1
        return remaining_parts, namespace

    async def execute(self, command: str, **kwargs) -> ToolResult:
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
            
            # Extract namespace and remaining command parts
            remaining_parts, namespace = self._extract_namespace_from_command(cmd_parts[1:])
            
            # Execute command based on type
            if main_cmd == "get":
                result = await self._handle_get_command(remaining_parts, namespace)
            elif main_cmd == "describe":
                result = await self._handle_describe_command(remaining_parts, namespace)
            elif main_cmd == "logs":
                result = await self._handle_logs_command(remaining_parts, namespace)
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
    
    def _format_deployments_list(self, deployments) -> str:
        """Format deployments list output"""
        if not deployments:
            return "No deployments found"
        
        output = ["NAME                    READY   UP-TO-DATE   AVAILABLE   AGE"]
        for deploy in deployments:
            ready = deploy.status.ready_replicas or 0
            total = deploy.spec.replicas or 0
            up_to_date = deploy.status.updated_replicas or 0
            available = deploy.status.available_replicas or 0
            age = self._calculate_age(deploy.metadata.creation_timestamp)
            
            output.append(
                f"{deploy.metadata.name:<22} {ready}/{total:<6} "
                f"{up_to_date:<13} {available:<12} {age}"
            )
        
        return "\n".join(output)
    
    def _format_nodes_list(self, nodes) -> str:
        """Format nodes list output"""
        if not nodes:
            return "No nodes found"
        
        output = ["NAME                     STATUS   ROLES   AGE   VERSION"]
        for node in nodes:
            status = "Ready" if node.status.conditions and any(
                c.type == "Ready" and c.status == "True" for c in node.status.conditions
            ) else "NotReady"
            
            roles = []
            if node.metadata.labels:
                for key, value in node.metadata.labels.items():
                    if key in ["node-role.kubernetes.io/control-plane", "node-role.kubernetes.io/master"]:
                        roles.append("control-plane")
                    elif key == "node-role.kubernetes.io/worker":
                        roles.append("worker")
            
            role_str = ",".join(roles) if roles else "<none>"
            age = self._calculate_age(node.metadata.creation_timestamp)
            version = node.status.node_info.kubelet_version if node.status.node_info else "unknown"
            
            output.append(
                f"{node.metadata.name:<25} {status:<8} {role_str:<7} {age:<6} {version}"
            )
        
        return "\n".join(output)
    
    def _format_namespaces_list(self, namespaces) -> str:
        """Format namespaces list output"""
        if not namespaces:
            return "No namespaces found"
        
        output = ["NAME              STATUS   AGE"]
        for ns in namespaces:
            status = ns.status.phase if ns.status else "Unknown"
            age = self._calculate_age(ns.metadata.creation_timestamp)
            
            output.append(f"{ns.metadata.name:<17} {status:<8} {age}")
        
        return "\n".join(output)
    
    def _format_pod_detail(self, pod) -> str:
        """Format pod detail output"""
        output = []
        output.append(f"Name:         {pod.metadata.name}")
        output.append(f"Namespace:    {pod.metadata.namespace}")
        output.append(f"Priority:     0")
        output.append(f"Node:         {pod.spec.node_name or '<none>'}")
        output.append(f"Start Time:   {pod.status.start_time or 'Unknown'}")
        output.append(f"Labels:       {', '.join([f'{k}={v}' for k, v in pod.metadata.labels.items()]) if pod.metadata.labels else '<none>'}")
        output.append(f"Annotations:  {', '.join([f'{k}={v}' for k, v in pod.metadata.annotations.items()]) if pod.metadata.annotations else '<none>'}")
        output.append(f"Status:       {pod.status.phase}")
        output.append(f"IP:           {pod.status.pod_ip or '<none>'}")
        output.append(f"Containers:")
        
        for i, container in enumerate(pod.spec.containers):
            output.append(f"  {container.name}:")
            output.append(f"    Image:         {container.image}")
            output.append(f"    Port:          {', '.join([str(p.container_port) for p in container.ports]) if container.ports else '<none>'}")
            output.append(f"    Host Port:     {', '.join([str(p.host_port) for p in container.ports if p.host_port]) if container.ports else '<none>'}")
            output.append(f"    State:         {self._get_container_state(pod.status.container_statuses, container.name) if pod.status.container_statuses else 'Unknown'}")
            output.append(f"    Ready:         {self._get_container_ready(pod.status.container_statuses, container.name) if pod.status.container_statuses else 'Unknown'}")
            output.append(f"    Restart Count: {self._get_container_restarts(pod.status.container_statuses, container.name) if pod.status.container_statuses else 'Unknown'}")
            output.append(f"    Environment:   {', '.join([f'{e.name}={e.value}' for e in container.env]) if container.env else '<none>'}")
            output.append(f"    Mounts:")
            for mount in container.volume_mounts or []:
                output.append(f"      {mount.name} from {mount.mount_path}")
        
        return "\n".join(output)
    
    def _format_service_detail(self, svc) -> str:
        """Format service detail output"""
        output = []
        output.append(f"Name:              {svc.metadata.name}")
        output.append(f"Namespace:         {svc.metadata.namespace}")
        output.append(f"Labels:            {', '.join([f'{k}={v}' for k, v in svc.metadata.labels.items()]) if svc.metadata.labels else '<none>'}")
        output.append(f"Annotations:       {', '.join([f'{k}={v}' for k, v in svc.metadata.annotations.items()]) if svc.metadata.annotations else '<none>'}")
        output.append(f"Selector:          {', '.join([f'{k}={v}' for k, v in svc.spec.selector.items()]) if svc.spec.selector else '<none>'}")
        output.append(f"Type:              {svc.spec.type}")
        output.append(f"IP:                {svc.spec.cluster_ip}")
        output.append(f"Port:              {svc.spec.ports[0].port if svc.spec.ports else '<none>'}/{svc.spec.ports[0].protocol if svc.spec.ports else '<none>'}")
        output.append(f"TargetPort:        {svc.spec.ports[0].target_port if svc.spec.ports else '<none>'}")
        output.append(f"Endpoints:         {', '.join([f'{ep.subsets[0].addresses[0].ip}:{ep.subsets[0].ports[0].port}' for ep in self.v1.list_namespaced_endpoints(svc.metadata.namespace).items if ep.metadata.name == svc.metadata.name and ep.subsets and ep.subsets[0].addresses]) if svc.spec.ports else '<none>'}")
        
        return "\n".join(output)
    
    def _format_deployment_detail(self, deploy) -> str:
        """Format deployment detail output"""
        output = []
        output.append(f"Name:                   {deploy.metadata.name}")
        output.append(f"Namespace:              {deploy.metadata.namespace}")
        output.append(f"CreationTimestamp:      {deploy.metadata.creation_timestamp}")
        output.append(f"Labels:                 {', '.join([f'{k}={v}' for k, v in deploy.metadata.labels.items()]) if deploy.metadata.labels else '<none>'}")
        output.append(f"Annotations:            {', '.join([f'{k}={v}' for k, v in deploy.metadata.annotations.items()]) if deploy.metadata.annotations else '<none>'}")
        output.append(f"Replicas:               {deploy.spec.replicas} desired | {deploy.status.updated_replicas or 0} updated | {deploy.status.ready_replicas or 0} ready | {deploy.status.available_replicas or 0} available")
        output.append(f"Selector:               {', '.join([f'{k}={v}' for k, v in deploy.spec.selector.match_labels.items()]) if deploy.spec.selector and deploy.spec.selector.match_labels else '<none>'}")
        output.append(f"Strategy Type:          {deploy.spec.strategy.type}")
        output.append(f"Min Ready Seconds:      {deploy.spec.min_ready_seconds or 0}")
        output.append(f"Pod Template:")
        output.append(f"  Labels:               {', '.join([f'{k}={v}' for k, v in deploy.spec.template.metadata.labels.items()]) if deploy.spec.template.metadata.labels else '<none>'}")
        output.append(f"  Containers:")
        
        for container in deploy.spec.template.spec.containers:
            output.append(f"   {container.name}:")
            output.append(f"    Image:      {container.image}")
            output.append(f"    Port:       {', '.join([str(p.container_port) for p in container.ports]) if container.ports else '<none>'}")
            output.append(f"    Host Port:  {', '.join([str(p.host_port) for p in container.ports if p.host_port]) if container.ports else '<none>'}")
            output.append(f"    Environment: {', '.join([f'{e.name}={e.value}' for e in container.env]) if container.env else '<none>'}")
        
        return "\n".join(output)
    
    def _format_node_detail(self, node) -> str:
        """Format node detail output"""
        output = []
        output.append(f"Name:               {node.metadata.name}")
        output.append(f"Roles:              {', '.join([f'{k}={v}' for k, v in node.metadata.labels.items() if 'node-role' in k]) if node.metadata.labels else '<none>'}")
        output.append(f"Labels:             {', '.join([f'{k}={v}' for k, v in node.metadata.labels.items()]) if node.metadata.labels else '<none>'}")
        output.append(f"Annotations:        {', '.join([f'{k}={v}' for k, v in node.metadata.annotations.items()]) if node.metadata.annotations else '<none>'}")
        output.append(f"CreationTimestamp:  {node.metadata.creation_timestamp}")
        output.append(f"Taints:             {', '.join([f'{t.key}={t.value}:{t.effect}' for t in node.spec.taints]) if node.spec.taints else '<none>'}")
        output.append(f"Unschedulable:      {node.spec.unschedulable or False}")
        output.append(f"Lease:")
        output.append(f"  HolderIdentity:  {node.metadata.name}")
        output.append(f"Conditions:")
        
        for condition in node.status.conditions or []:
            output.append(f"  Type                 Status  LastHeartbeatTime                 LastTransitionTime                Reason                       Message")
            output.append(f"  ----                 ------  -----------------                 ------------------                ------                       -------")
            output.append(f"  {condition.type:<20} {condition.status:<7} {condition.last_heartbeat_time:<32} {condition.last_transition_time:<32} {condition.reason:<28} {condition.message}")
        
        output.append(f"Addresses:")
        for addr in node.status.addresses or []:
            output.append(f"  {addr.type:<10} {addr.address}")
        
        output.append(f"Capacity:")
        for resource, quantity in node.status.capacity.items():
            output.append(f"  {resource:<10} {quantity}")
        
        output.append(f"Allocatable:")
        for resource, quantity in node.status.allocatable.items():
            output.append(f"  {resource:<10} {quantity}")
        
        output.append(f"System Info:")
        if node.status.node_info:
            output.append(f"  Machine ID:     {node.status.node_info.machine_id}")
            output.append(f"  System UUID:    {node.status.node_info.system_uuid}")
            output.append(f"  Boot ID:        {node.status.node_info.boot_id}")
            output.append(f"  Kernel Version: {node.status.node_info.kernel_version}")
            output.append(f"  OS Image:       {node.status.node_info.os_image}")
            output.append(f"  Container Runtime Version: {node.status.node_info.container_runtime_version}")
            output.append(f"  Kubelet Version: {node.status.node_info.kubelet_version}")
            output.append(f"  Kube-Proxy Version: {node.status.node_info.kube_proxy_version}")
        
        return "\n".join(output)
    
    def _format_namespace_detail(self, ns) -> str:
        """Format namespace detail output"""
        output = []
        output.append(f"Name:         {ns.metadata.name}")
        output.append(f"Labels:       {', '.join([f'{k}={v}' for k, v in ns.metadata.labels.items()]) if ns.metadata.labels else '<none>'}")
        output.append(f"Annotations:  {', '.join([f'{k}={v}' for k, v in ns.metadata.annotations.items()]) if ns.metadata.annotations else '<none>'}")
        output.append(f"Status:       {ns.status.phase}")
        output.append(f"Age:          {self._calculate_age(ns.metadata.creation_timestamp)}")
        
        return "\n".join(output)
    
    def _format_ingress_detail(self, ingress) -> str:
        """Format ingress detail output"""
        output = []
        output.append(f"Name:             {ingress.metadata.name}")
        output.append(f"Namespace:        {ingress.metadata.namespace}")
        output.append(f"Address:          {', '.join([addr.ip for addr in ingress.status.load_balancer.ingress]) if ingress.status.load_balancer and ingress.status.load_balancer.ingress else '<none>'}")
        output.append(f"Default backend:  <none>")
        output.append(f"Rules:")
        
        for rule in ingress.spec.rules or []:
            output.append(f"  Host             Path  Backends")
            output.append(f"  ----             ----  --------")
            if rule.http:
                for path in rule.http.paths:
                    backend = path.backend
                    if hasattr(backend, 'service'):
                        output.append(f"  {rule.host:<16} {path.path:<5} {backend.service.name}:{backend.service.port.number if hasattr(backend.service.port, 'number') else backend.service.port}")
                    else:
                        output.append(f"  {rule.host:<16} {path.path:<5} {backend.resource.name}")
            else:
                output.append(f"  {rule.host:<16} *     <none>")
        
        output.append(f"Annotations:")
        for key, value in ingress.metadata.annotations.items():
            output.append(f"  {key}: {value}")
        
        return "\n".join(output)
    
    def _format_configmap_detail(self, cm) -> str:
        """Format configmap detail output"""
        output = []
        output.append(f"Name:         {cm.metadata.name}")
        output.append(f"Namespace:    {cm.metadata.namespace}")
        output.append(f"Labels:       {', '.join([f'{k}={v}' for k, v in cm.metadata.labels.items()]) if cm.metadata.labels else '<none>'}")
        output.append(f"Annotations:  {', '.join([f'{k}={v}' for k, v in cm.metadata.annotations.items()]) if cm.metadata.annotations else '<none>'}")
        output.append(f"Data")
        output.append(f"=====")
        
        for key, value in cm.data.items():
            output.append(f"{key}")
        
        output.append(f"BinaryData")
        output.append(f"=====")
        
        for key, value in cm.binary_data.items():
            output.append(f"{key}")
        
        return "\n".join(output)
    
    def _format_secret_detail(self, secret) -> str:
        """Format secret detail output"""
        output = []
        output.append(f"Name:         {secret.metadata.name}")
        output.append(f"Namespace:    {secret.metadata.namespace}")
        output.append(f"Labels:       {', '.join([f'{k}={v}' for k, v in secret.metadata.labels.items()]) if secret.metadata.labels else '<none>'}")
        output.append(f"Annotations:  {', '.join([f'{k}={v}' for k, v in secret.metadata.annotations.items()]) if secret.metadata.annotations else '<none>'}")
        output.append(f"Type:         {secret.type}")
        output.append(f"Data")
        output.append(f"=====")
        
        for key, value in secret.data.items():
            output.append(f"{key}")
        
        return "\n".join(output)
    
    def _get_container_state(self, container_statuses, container_name: str) -> str:
        """Get container state string"""
        if not container_statuses:
            return "Unknown"
        
        for status in container_statuses:
            if status.name == container_name:
                if status.state.running:
                    return "Running"
                elif status.state.waiting:
                    return f"Waiting ({status.state.waiting.reason})"
                elif status.state.terminated:
                    return f"Terminated ({status.state.terminated.reason})"
                else:
                    return "Unknown"
        return "Unknown"
    
    def _get_container_ready(self, container_statuses, container_name: str) -> str:
        """Get container ready status"""
        if not container_statuses:
            return "Unknown"
        
        for status in container_statuses:
            if status.name == container_name:
                return str(status.ready)
        return "Unknown"
    
    def _get_container_restarts(self, container_statuses, container_name: str) -> str:
        """Get container restart count"""
        if not container_statuses:
            return "Unknown"
        
        for status in container_statuses:
            if status.name == container_name:
                return str(status.restart_count)
        return "Unknown"

    async def _handle_describe_command(self, args: List[str], namespace: str) -> str:
        """Handle kubectl describe commands"""
        if not args:
            return "Usage: describe <resource> [name]"
        
        resource_type = args[0].lower()
        resource_name = args[1] if len(args) > 1 else None

        try:
            if resource_type in ["pod", "pods"]:
                return await self._describe_pod(resource_name, namespace)
            elif resource_type in ["service", "services", "svc"]:
                return await self._describe_service(resource_name, namespace)
            elif resource_type in ["deployment", "deployments", "deploy"]:
                return await self._describe_deployment(resource_name, namespace)
            elif resource_type in ["ingress", "ingresses", "ing"]:
                return await self._describe_ingress(resource_name, namespace)
            elif resource_type in ["configmap", "configmaps", "cm"]:
                return await self._describe_configmap(resource_name, namespace)
            elif resource_type in ["secret", "secrets", "sec"]:
                return await self._describe_secret(resource_name, namespace)    
            else:
                return f"Resource type '{resource_type}' not supported yet"
        except ApiException as e:
            return f"Error getting {resource_type}: {e.reason}"
    
    async def _describe_pod(self, pod_name: str, namespace: str) -> str:
        """Describe pod"""
        try:
            pod = self.v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            return self._format_pod_detail(pod)
        except ApiException as e:
            return f"Error getting pod: {e.reason}"
    
    async def _describe_service(self, service_name: str, namespace: str) -> str:
        """Describe service"""
        try:
            svc = self.v1.read_namespaced_service(name=service_name, namespace=namespace)
            return self._format_service_detail(svc)
        except ApiException as e:
            return f"Error getting service: {e.reason}"
    
    async def _describe_deployment(self, deployment_name: str, namespace: str) -> str:
        """Describe deployment"""
        try:
            deploy = self.apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
            return self._format_deployment_detail(deploy)
        except ApiException as e:
            return f"Error getting deployment: {e.reason}"
    
    async def _describe_ingress(self, ingress_name: str, namespace: str) -> str:
        """Describe ingress"""
        try:
            ingress = self.networking_v1.read_namespaced_ingress(name=ingress_name, namespace=namespace)
            return self._format_ingress_detail(ingress)
        except ApiException as e:
            return f"Error getting ingress: {e.reason}"
    
    async def _describe_configmap(self, configmap_name: str, namespace: str) -> str:
        """Describe configmap"""
        try:
            cm = self.v1.read_namespaced_config_map(name=configmap_name, namespace=namespace)
            return self._format_configmap_detail(cm)
        except ApiException as e:
            return f"Error getting configmap: {e.reason}"
    
    async def _describe_secret(self, secret_name: str, namespace: str) -> str:
        """Describe secret"""
        try:
            secret = self.v1.read_namespaced_secret(name=secret_name, namespace=namespace)
            return self._format_secret_detail(secret)
        except ApiException as e:
            return f"Error getting secret: {e.reason}"
    
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
                tail_lines=100
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
            )
        ]