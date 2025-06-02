"""
Main agent controller for orchestrating troubleshooting workflows
"""
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from llm.provider import LLMProvider, Message, LLMResponse
from tools.registry import ToolRegistry
from tools.base import ToolResult

logger = logging.getLogger(__name__)

@dataclass
class ConversationContext:
    """Context for current troubleshooting session"""
    user_query: str
    symptoms: List[str]
    cluster_info: Dict[str, Any]
    namespace: str
    suspected_components: List[str]
    investigation_steps: List[str]

class AgentController:
    """Main controller for the troubleshooting agent"""
    
    def __init__(
        self, 
        llm_provider: LLMProvider, 
        tool_registry: ToolRegistry,
        max_iterations: int = 20,
        conversation_memory: int = 10
    ):
        self.llm = llm_provider
        self.tools = tool_registry
        self.max_iterations = max_iterations
        self.conversation_memory = conversation_memory
        
        self.conversation_history: List[Message] = []
        self.context: Optional[ConversationContext] = None
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt with available tools"""
        tools_info = []
        for tool in self.tools.list_tools():
            params = [p.name for p in tool.get_parameters()]
            tools_info.append(f"- {tool.name}: {tool.description} (params: {', '.join(params)})")
        
        return f"""You are an expert Kubernetes and Istio troubleshooting assistant. Your goal is to help diagnose and resolve issues systematically.

AVAILABLE TOOLS:
{chr(10).join(tools_info)}

TROUBLESHOOTING METHODOLOGY:
1. **Gather Information**: Always start by understanding the problem and current cluster state
2. **Systematic Investigation**: Use tools to collect relevant data before making assumptions
3. **Pattern Recognition**: Look for common issues like:
   - Pod startup failures (image pull, resource limits, configuration)
   - Network connectivity problems (services, endpoints, DNS)
   - Istio service mesh issues (proxy status, configuration, routing)
   - Resource constraints (CPU, memory, storage)
4. **Root Cause Analysis**: Correlate findings to identify the actual cause
5. **Solution Recommendation**: Provide clear, actionable steps to resolve issues

TOOL USAGE GUIDELINES:
- Use kubectl to inspect cluster resources and status
- Check pod logs when investigating application issues
- Use Istio tools for service mesh related problems
- Always verify your findings with multiple data points

RESPONSE FORMAT:
When using tools, explain:
- Why you're using each tool
- What you're looking for
- What the results indicate
- Next steps based on findings

Be concise but thorough. Focus on actionable insights."""

    async def process_query(self, user_input: str, namespace: str = "default") -> str:
        """Process user query and return response"""
        logger.info(f"Processing query: {user_input[:100]}...")
        
        # Add user message to history
        self.conversation_history.append(Message("user", user_input))
        
        # Trim conversation history if needed
        if len(self.conversation_history) > self.conversation_memory * 2:
            # Keep system message and recent messages
            recent_messages = self.conversation_history[-self.conversation_memory:]
            self.conversation_history = recent_messages
        
        # Initialize context for new conversation
        if not self.context or self._is_new_issue(user_input):
            self.context = ConversationContext(
                user_query=user_input,
                symptoms=[],
                cluster_info={},
                namespace=namespace,
                suspected_components=[],
                investigation_steps=[]
            )
        
        # Main reasoning loop
        iteration = 0
        while iteration < self.max_iterations:
            try:
                # Prepare messages for LLM
                messages = [Message("system", self.system_prompt)] + self.conversation_history
                
                # Get LLM response
                logger.debug(f"Iteration {iteration + 1}: Getting LLM response")
                response = await self.llm.chat_completion(messages)
                
                # Check if LLM wants to use tools
                tool_calls = self._extract_tool_calls(response.content)
                logger.debug(f"Tool calls: {tool_calls}")
                
                if tool_calls:
                    # Execute tools and add results
                    tool_results = await self._execute_tools(tool_calls)
                    
                    # Add LLM response and tool results to conversation
                    self.conversation_history.append(Message("assistant", response.content))
                    
                    # Format tool results for LLM
                    results_text = self._format_tool_results(tool_results)
                    self.conversation_history.append(Message("user", f"Tool Results:\n{results_text}"))
                    
                    iteration += 1
                else:
                    # Final response - no more tools needed
                    self.conversation_history.append(Message("assistant", response.content))
                    return response.content
                    
            except Exception as e:
                logger.error(f"Error in iteration {iteration}: {e}")
                return f"I encountered an error while troubleshooting: {str(e)}. Please try rephrasing your question or provide more specific details."
        
        # Max iterations reached
        return ("I've reached my analysis limit for this query. Based on my investigation, "
                "I recommend reviewing the tool outputs above for insights. "
                "Please provide more specific information or ask about a particular aspect of the issue.")
    
    def _is_new_issue(self, user_input: str) -> bool:
        """Determine if this is a new issue or continuation"""
        new_issue_indicators = [
            "new problem", "different issue", "another error", 
            "start over", "new question"
        ]
        return any(indicator in user_input.lower() for indicator in new_issue_indicators)
    
    def _extract_tool_calls(self, llm_response: str) -> List[Dict[str, Any]]:
        """Extract tool calls from LLM response"""
        tool_calls = []
        
        # Simple pattern matching for tool calls
        # In production, you might want more sophisticated parsing
        lines = llm_response.split('\n')
        
        for line in lines:
            line = line.strip()
            logger.debug(f"extract_tool_calls line: {line}")
            # Look for patterns like: "kubectl get pods" or "Tool: kubectl, Command: get pods"
            if line.startswith('kubectl '):
                command = line[8:].strip()  # Remove 'kubectl '
                tool_calls.append({
                    "tool": "kubectl",
                    "parameters": {"command": command, "namespace": self.context.namespace}
                })
            
            elif line.startswith('istio '):
                # Parse istio commands like "istio proxy_status"
                parts = line[6:].strip().split(' ', 1)
                action = parts[0]
                params = {"action": action}
                if len(parts) > 1:
                    # Additional parameters
                    params.update({"service": parts[1]})
                tool_calls.append({
                    "tool": "istio",
                    "parameters": params
                })
            
            # Pattern: "Let me check [description] using [tool]"
            elif "let me check" in line.lower() and "using" in line.lower():
                if "kubectl" in line.lower():
                    # Extract command from context
                    if "pods" in line.lower():
                        tool_calls.append({
                            "tool": "kubectl",
                            "parameters": {"command": "get pods", "namespace": self.context.namespace}
                        })
                    elif "services" in line.lower():
                        tool_calls.append({
                            "tool": "kubectl",
                            "parameters": {"command": "get services", "namespace": self.context.namespace}
                        })
        
        # If no explicit tool calls found but should investigate, add default investigation
        if not tool_calls and self._should_start_investigation(llm_response):
            tool_calls.append({
                "tool": "kubectl",
                "parameters": {"command": "get pods", "namespace": self.context.namespace}
            })
        
        return tool_calls
    
    def _should_start_investigation(self, llm_response: str) -> bool:
        """Determine if we should start basic investigation"""
        investigation_triggers = [
            "let me investigate", "let me check", "i'll examine",
            "let me look at", "i need to see", "first, let me"
        ]
        return any(trigger in llm_response.lower() for trigger in investigation_triggers)
    
    async def _execute_tools(self, tool_calls: List[Dict[str, Any]]) -> List[ToolResult]:
        """Execute multiple tool calls"""
        results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call["tool"]
            parameters = tool_call["parameters"]
            
            logger.debug(f"Executing tool: {tool_name} with params: {parameters}")
            
            try:
                result = await self.tools.execute_tool(tool_name, **parameters)
                results.append(result)
                
                # Update context with findings
                self._update_context_from_result(tool_name, result)
                
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                results.append(ToolResult(
                    success=False,
                    error=str(e),
                    tool_name=tool_name
                ))
        
        return results
    
    def _update_context_from_result(self, tool_name: str, result: ToolResult):
        """Update conversation context based on tool results"""
        if not result.success or not self.context:
            return
        
        # Extract insights from kubectl results
        if tool_name == "kubectl" and isinstance(result.data, str):
            data = result.data.lower()
            
            # Look for error conditions
            if "crashloopbackoff" in data:
                self.context.symptoms.append("Pod in CrashLoopBackOff")
                self.context.suspected_components.append("application startup")
            
            if "imagepullbackoff" in data or "errimagepull" in data:
                self.context.symptoms.append("Image pull failure")
                self.context.suspected_components.append("container registry")
            
            if "pending" in data:
                self.context.symptoms.append("Pod stuck in Pending")
                self.context.suspected_components.append("scheduling/resources")
            
            # Count running vs problematic pods
            lines = result.data.split('\n')
            if len(lines) > 1:  # Has header + data
                running_count = sum(1 for line in lines[1:] if "running" in line.lower())
                total_count = len(lines) - 1
                self.context.cluster_info["pod_health"] = f"{running_count}/{total_count} running"
    
    def _format_tool_results(self, results: List[ToolResult]) -> str:
        """Format tool results for LLM consumption"""
        formatted_results = []
        
        for result in results:
            if result.success:
                formatted_results.append(
                    f"✅ {result.tool_name} executed successfully:\n{result.data}"
                )
            else:
                formatted_results.append(
                    f"❌ {result.tool_name} failed: {result.error}"
                )
        
        return "\n\n".join(formatted_results)
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get summary of current conversation"""
        return {
            "message_count": len(self.conversation_history),
            "context": self.context.__dict__ if self.context else None,
            "last_message": self.conversation_history[-1].content if self.conversation_history else None
        }
    
    def reset_conversation(self):
        """Reset conversation state"""
        self.conversation_history = []
        self.context = None
        logger.info("Conversation reset")

class TroubleshootingWorkflows:
    """Pre-defined troubleshooting workflows"""
    
    @staticmethod
    def pod_startup_issues() -> List[Dict[str, Any]]:
        """Workflow for pod startup problems"""
        return [
            {"tool": "kubectl", "parameters": {"command": "get pods"}},
            {"tool": "kubectl", "parameters": {"command": "describe pod <pod-name>"}},
            {"tool": "kubectl", "parameters": {"command": "logs <pod-name>"}}
        ]
    
    @staticmethod
    def service_connectivity() -> List[Dict[str, Any]]:
        """Workflow for service connectivity issues"""
        return [
            {"tool": "kubectl", "parameters": {"command": "get services"}},
            {"tool": "kubectl", "parameters": {"command": "get endpoints"}},
            {"tool": "kubectl", "parameters": {"command": "describe service <service-name>"}},
            {"tool": "istio", "parameters": {"action": "proxy_status"}}
        ]
    
    @staticmethod
    def istio_mesh_issues() -> List[Dict[str, Any]]:
        """Workflow for Istio service mesh problems"""
        return [
            {"tool": "istio", "parameters": {"action": "proxy_status"}},
            {"tool": "istio", "parameters": {"action": "config_dump"}},
            {"tool": "kubectl", "parameters": {"command": "get pods -n istio-system"}},
            {"tool": "istio", "parameters": {"action": "analyze_traffic"}}
        ]