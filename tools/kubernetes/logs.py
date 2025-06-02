"""
Kubernetes logs analysis and aggregation tools
"""
import asyncio
import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from kubernetes import client
from kubernetes.client.rest import ApiException

from ..base import AsyncTool, ToolResult, ToolParameter, ToolCategory

logger = logging.getLogger(__name__)

class LogsTool(AsyncTool):
    """Tool for analyzing Kubernetes pod logs"""
    
    def __init__(self):
        super().__init__(
            name="logs",
            description="Analyze and search Kubernetes pod logs for troubleshooting",
            category=ToolCategory.KUBERNETES
        )
        self._init_k8s_client()
    
    def _init_k8s_client(self):
        """Initialize Kubernetes client"""
        try:
            from kubernetes import config
            try:
                config.load_incluster_config()
            except:
                config.load_kube_config()
            
            self.core_api = client.CoreV1Api()
            
        except Exception as e:
            logger.warning(f"Could not initialize Kubernetes client: {e}")
            self.core_api = None
    
    async def execute(self, action: str, **kwargs) -> ToolResult:
        """Execute log analysis commands"""
        if not self.core_api:
            return ToolResult(
                success=False,
                error="Kubernetes client not available"
            )
        
        try:
            if action == "get":
                return await self._get_logs(**kwargs)
            elif action == "search":
                return await self._search_logs(**kwargs)
            elif action == "analyze":
                return await self._analyze_logs(**kwargs)
            elif action == "errors":
                return await self._find_errors(**kwargs)
            elif action == "tail":
                return await self._tail_logs(**kwargs)
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown action: {action}. Available: get, search, analyze, errors, tail"
                )
        except Exception as e:
            logger.error(f"Error in logs tool: {e}")
            return ToolResult(success=False, error=str(e))
    
    async def _get_logs(self, pod_name: str, namespace: str = "default", **kwargs) -> ToolResult:
        """Get logs from a specific pod"""
        try:
            container = kwargs.get("container")
            lines = kwargs.get("lines", 100)
            since_seconds = kwargs.get("since_seconds")
            
            # Get pod info first
            try:
                pod = self.core_api.read_namespaced_pod(name=pod_name, namespace=namespace)
            except ApiException as e:
                if e.status == 404:
                    return ToolResult(
                        success=False,
                        error=f"Pod {pod_name} not found in namespace {namespace}"
                    )
                raise
            
            # If no container specified and pod has multiple containers, list them
            containers = [c.name for c in pod.spec.containers]
            if not container and len(containers) > 1:
                return ToolResult(
                    success=False,
                    error=f"Pod has multiple containers: {', '.join(containers)}. Please specify container name.",
                    data={"containers": containers}
                )
            
            # Use first container if not specified
            if not container:
                container = containers[0] if containers else None
            
            # Get logs
            try:
                logs = self.core_api.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace,
                    container=container,
                    tail_lines=lines,
                    since_seconds=since_seconds
                )
                
                # Analyze the logs
                analysis = self._analyze_log_content(logs)
                
                return ToolResult(
                    success=True,
                    data={
                        "logs": logs,
                        "analysis": analysis,
                        "container": container,
                        "lines_retrieved": len(logs.split('\n')) if logs else 0
                    },
                    metadata={
                        "pod": pod_name,
                        "namespace": namespace,
                        "container": container
                    }
                )
                
            except ApiException as e:
                if e.status == 400:
                    return ToolResult(
                        success=False,
                        error=f"Cannot get logs: {e.reason}. Pod may not be running or container may not exist."
                    )
                raise
        
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get logs: {e}")
    
    async def _search_logs(self, pod_name: str, pattern: str, namespace: str = "default", **kwargs) -> ToolResult:
        """Search for patterns in pod logs"""
        try:
            # First get the logs
            log_result = await self._get_logs(pod_name, namespace, **kwargs)
            if not log_result.success:
                return log_result
            
            logs = log_result.data["logs"]
            if not logs:
                return ToolResult(
                    success=True,
                    data={
                        "matches": [],
                        "total_matches": 0,
                        "pattern": pattern
                    }
                )
            
            # Search for pattern
            case_sensitive = kwargs.get("case_sensitive", False)
            flags = 0 if case_sensitive else re.IGNORECASE
            
            matches = []
            lines = logs.split('\n')
            
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line, flags):
                    matches.append({
                        "line_number": i,
                        "content": line.strip(),
                        "timestamp": self._extract_timestamp(line)
                    })
            
            return ToolResult(
                success=True,
                data={
                    "matches": matches,
                    "total_matches": len(matches),
                    "pattern": pattern,
                    "total_lines": len(lines)
                },
                metadata={
                    "pod": pod_name,
                    "namespace": namespace
                }
            )
        
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to search logs: {e}")
    
    async def _analyze_logs(self, pod_name: str, namespace: str = "default", **kwargs) -> ToolResult:
        """Analyze logs for common issues and patterns"""
        try:
            # Get logs
            log_result = await self._get_logs(pod_name, namespace, lines=500, **kwargs)
            if not log_result.success:
                return log_result
            
            logs = log_result.data["logs"]
            if not logs:
                return ToolResult(
                    success=True,
                    data={"analysis": "No logs available for analysis"}
                )
            
            analysis = self._comprehensive_log_analysis(logs)
            
            return ToolResult(
                success=True,
                data=analysis,
                metadata={
                    "pod": pod_name,
                    "namespace": namespace
                }
            )
        
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to analyze logs: {e}")
    
    async def _find_errors(self, pod_name: str, namespace: str = "default", **kwargs) -> ToolResult:
        """Find error messages in logs"""
        try:
            error_patterns = [
                r"(?i)\berror\b",
                r"(?i)\bfatal\b",
                r"(?i)\bexception\b",
                r"(?i)\bfailed\b",
                r"(?i)\bpanic\b",
                r"(?i)\bstack trace\b",
                r"\b5\d{2}\b",  # HTTP 5xx errors
                r"\b4\d{2}\b",  # HTTP 4xx errors
            ]
            
            all_errors = []
            
            for pattern in error_patterns:
                search_result = await self._search_logs(pod_name, pattern, namespace, **kwargs)
                if search_result.success and search_result.data["matches"]:
                    all_errors.extend(search_result.data["matches"])
            
            # Remove duplicates and sort by line number
            seen_lines = set()
            unique_errors = []
            for error in all_errors:
                if error["line_number"] not in seen_lines:
                    unique_errors.append(error)
                    seen_lines.add(error["line_number"])
            
            unique_errors.sort(key=lambda x: x["line_number"])
            
            # Categorize errors
            categorized_errors = self._categorize_errors(unique_errors)
            
            return ToolResult(
                success=True,
                data={
                    "errors": unique_errors,
                    "total_errors": len(unique_errors),
                    "categories": categorized_errors
                },
                metadata={
                    "pod": pod_name,
                    "namespace": namespace
                }
            )
        
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to find errors: {e}")
    
    async def _tail_logs(self, pod_name: str, namespace: str = "default", **kwargs) -> ToolResult:
        """Get recent logs (last few minutes)"""
        try:
            # Get logs from last 5 minutes
            since_seconds = kwargs.get("since_seconds", 300)  # 5 minutes
            
            result = await self._get_logs(
                pod_name, 
                namespace, 
                since_seconds=since_seconds,
                **kwargs
            )
            
            if result.success:
                result.metadata["tail_duration"] = f"{since_seconds} seconds"
            
            return result
        
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to tail logs: {e}")
    
    def _analyze_log_content(self, logs: str) -> Dict[str, Any]:
        """Basic log content analysis"""
        if not logs:
            return {"summary": "No logs to analyze"}
        
        lines = logs.split('\n')
        analysis = {
            "total_lines": len(lines),
            "empty_lines": sum(1 for line in lines if not line.strip()),
            "log_levels": {},
            "timestamps": {
                "first": None,
                "last": None,
                "span": None
            },
            "issues": []
        }
        
        # Count log levels
        log_level_patterns = {
            "ERROR": r"(?i)\b(error|err)\b",
            "WARN": r"(?i)\b(warn|warning)\b",
            "INFO": r"(?i)\b(info|information)\b",
            "DEBUG": r"(?i)\b(debug|dbg)\b",
            "FATAL": r"(?i)\b(fatal|panic)\b"
        }
        
        timestamps = []
        
        for line in lines:
            if not line.strip():
                continue
            
            # Count log levels
            for level, pattern in log_level_patterns.items():
                if re.search(pattern, line):
                    analysis["log_levels"][level] = analysis["log_levels"].get(level, 0) + 1
            
            # Extract timestamps
            timestamp = self._extract_timestamp(line)
            if timestamp:
                timestamps.append(timestamp)
        
        # Analyze timestamps
        if timestamps:
            analysis["timestamps"]["first"] = min(timestamps)
            analysis["timestamps"]["last"] = max(timestamps)
            analysis["timestamps"]["span"] = str(max(timestamps) - min(timestamps))
        
        # Identify issues
        if analysis["log_levels"].get("ERROR", 0) > 0:
            analysis["issues"].append(f"Found {analysis['log_levels']['ERROR']} error messages")
        
        if analysis["log_levels"].get("FATAL", 0) > 0:
            analysis["issues"].append(f"Found {analysis['log_levels']['FATAL']} fatal messages")
        
        return analysis
    
    def _comprehensive_log_analysis(self, logs: str) -> Dict[str, Any]:
        """Comprehensive log analysis for troubleshooting"""
        basic_analysis = self._analyze_log_content(logs)
        
        lines = logs.split('\n')
        
        # Advanced patterns
        patterns = {
            "connection_errors": r"(?i)(connection.*refused|connection.*timeout|connection.*reset)",
            "authentication_errors": r"(?i)(authentication.*failed|unauthorized|forbidden|access.*denied)",
            "resource_errors": r"(?i)(out of memory|disk.*full|resource.*exhausted|quota.*exceeded)",
            "network_errors": r"(?i)(network.*unreachable|dns.*resolution.*failed|timeout)",
            "startup_errors": r"(?i)(failed to start|initialization.*failed|startup.*error)",
            "configuration_errors": r"(?i)(configuration.*error|invalid.*config|missing.*config)",
            "dependency_errors": r"(?i)(service.*unavailable|dependency.*failed|external.*service)"
        }
        
        pattern_matches = {}
        for pattern_name, pattern in patterns.items():
            matches = []
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    matches.append({
                        "line": i,
                        "content": line.strip()
                    })
            if matches:
                pattern_matches[pattern_name] = matches
        
        # Performance indicators
        performance_indicators = self._extract_performance_metrics(logs)
        
        # Generate recommendations
        recommendations = []
        if "connection_errors" in pattern_matches:
            recommendations.append("Check network connectivity and service endpoints")
        if "authentication_errors" in pattern_matches:
            recommendations.append("Verify authentication credentials and RBAC permissions")
        if "resource_errors" in pattern_matches:
            recommendations.append("Check resource limits and node capacity")
        if "startup_errors" in pattern_matches:
            recommendations.append("Review container configuration and dependencies")
        if "configuration_errors" in pattern_matches:
            recommendations.append("Validate configuration files and environment variables")
        
        return {
            "basic_analysis": basic_analysis,
            "pattern_matches": pattern_matches,
            "performance_metrics": performance_indicators,
            "recommendations": recommendations,
            "severity": self._assess_severity(basic_analysis, pattern_matches)
        }
    
    def _extract_performance_metrics(self, logs: str) -> Dict[str, Any]:
        """Extract performance-related metrics from logs"""
        metrics = {
            "response_times": [],
            "error_rates": {},
            "throughput_indicators": []
        }
        
        # Look for common performance patterns
        response_time_pattern = r"(?i)(\d+(?:\.\d+)?)\s*(ms|milliseconds|s|seconds)"
        throughput_pattern = r"(?i)(\d+)\s*(requests?|req|rps|qps)"
        
        lines = logs.split('\n')
        for line in lines:
            # Extract response times
            for match in re.finditer(response_time_pattern, line):
                value = float(match.group(1))
                unit = match.group(2).lower()
                
                # Convert to milliseconds
                if unit.startswith('s'):
                    value *= 1000
                
                metrics["response_times"].append(value)
            
            # Extract throughput indicators
            for match in re.finditer(throughput_pattern, line):
                value = int(match.group(1))
                metrics["throughput_indicators"].append(value)
        
        # Calculate statistics
        if metrics["response_times"]:
            response_times = metrics["response_times"]
            metrics["response_time_stats"] = {
                "min": min(response_times),
                "max": max(response_times),
                "avg": sum(response_times) / len(response_times),
                "count": len(response_times)
            }
        
        return metrics
    
    def _assess_severity(self, basic_analysis: Dict, pattern_matches: Dict) -> str:
        """Assess overall severity of issues found in logs"""
        error_count = basic_analysis.get("log_levels", {}).get("ERROR", 0)
        fatal_count = basic_analysis.get("log_levels", {}).get("FATAL", 0)
        
        critical_patterns = ["resource_errors", "startup_errors", "dependency_errors"]
        critical_issues = sum(1 for pattern in critical_patterns if pattern in pattern_matches)
        
        if fatal_count > 0 or critical_issues >= 2:
            return "CRITICAL"
        elif error_count > 10 or critical_issues >= 1:
            return "HIGH"
        elif error_count > 0:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _categorize_errors(self, errors: List[Dict]) -> Dict[str, List[Dict]]:
        """Categorize errors by type"""
        categories = {
            "network": [],
            "authentication": [],
            "resource": [],
            "configuration": [],
            "application": [],
            "other": []
        }
        
        category_patterns = {
            "network": r"(?i)(connection|network|timeout|dns|socket)",
            "authentication": r"(?i)(auth|login|credential|permission|forbidden|unauthorized)",
            "resource": r"(?i)(memory|disk|cpu|quota|limit|resource)",
            "configuration": r"(?i)(config|setting|parameter|environment|variable)",
            "application": r"(?i)(exception|null|undefined|syntax|logic)"
        }
        
        for error in errors:
            content = error["content"]
            categorized = False
            
            for category, pattern in category_patterns.items():
                if re.search(pattern, content):
                    categories[category].append(error)
                    categorized = True
                    break
            
            if not categorized:
                categories["other"].append(error)
        
        return categories
    
    def _extract_timestamp(self, line: str) -> Optional[datetime]:
        """Extract timestamp from log line"""
        # Common timestamp patterns
        patterns = [
            r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)",
            r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})",
            r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})",
            r"([A-Za-z]{3} \d{1,2} \d{2}:\d{2}:\d{2})"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    timestamp_str = match.group(1)
                    # Try different parsing formats
                    formats = [
                        "%Y-%m-%dT%H:%M:%S.%fZ",
                        "%Y-%m-%dT%H:%M:%SZ",
                        "%Y-%m-%d %H:%M:%S.%f",
                        "%Y-%m-%d %H:%M:%S",
                        "%m/%d/%Y %H:%M:%S",
                        "%Y/%m/%d %H:%M:%S"
                    ]
                    
                    for fmt in formats:
                        try:
                            return datetime.strptime(timestamp_str, fmt)
                        except ValueError:
                            continue
                except:
                    pass
        
        return None
    
    def get_parameters(self) -> List[ToolParameter]:
        """Get tool parameters"""
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform",
                required=True,
                enum_values=["get", "search", "analyze", "errors", "tail"]
            ),
            ToolParameter(
                name="pod_name",
                type="string",
                description="Name of the pod to get logs from",
                required=True
            ),
            ToolParameter(
                name="namespace",
                type="string",
                description="Kubernetes namespace",
                required=False,
                default="default"
            ),
            ToolParameter(
                name="container",
                type="string",
                description="Container name (for multi-container pods)",
                required=False
            ),
            ToolParameter(
                name="lines",
                type="integer",
                description="Number of lines to retrieve",
                required=False,
                default=100
            ),
            ToolParameter(
                name="since_seconds",
                type="integer",
                description="Get logs from last N seconds",
                required=False
            ),
            ToolParameter(
                name="pattern",
                type="string",
                description="Search pattern (for search action)",
                required=False
            ),
            ToolParameter(
                name="case_sensitive",
                type="boolean",
                description="Case sensitive search",
                required=False,
                default=False
            )
        ]