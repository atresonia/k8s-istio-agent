"""
Tool registry for managing and discovering tools
"""
import logging
from typing import Dict, List, Optional, Set
from .base import Tool, ToolCategory, ToolResult

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Registry for managing tools"""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._categories: Dict[ToolCategory, Set[str]] = {
            category: set() for category in ToolCategory
        }
    
    def register(self, tool: Tool) -> None:
        """Register a tool"""
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, overwriting")
        
        self._tools[tool.name] = tool
        self._categories[tool.category].add(tool.name)
        
        logger.info(f"Registered tool: {tool.name} (category: {tool.category.value})")
    
    def unregister(self, tool_name: str) -> bool:
        """Unregister a tool"""
        if tool_name not in self._tools:
            return False
        
        tool = self._tools[tool_name]
        del self._tools[tool_name]
        self._categories[tool.category].discard(tool_name)
        
        logger.info(f"Unregistered tool: {tool_name}")
        return True
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self._tools.get(name)
    
    def list_tools(self, category: Optional[ToolCategory] = None, enabled_only: bool = True) -> List[Tool]:
        """List tools, optionally filtered by category"""
        tools = []
        
        if category:
            tool_names = self._categories.get(category, set())
            tools = [self._tools[name] for name in tool_names if name in self._tools]
        else:
            tools = list(self._tools.values())
        
        if enabled_only:
            tools = [tool for tool in tools if tool.enabled]
        
        return tools
    
    def get_tool_names(self, category: Optional[ToolCategory] = None) -> List[str]:
        """Get list of tool names"""
        return [tool.name for tool in self.list_tools(category)]
    
    def enable_tool(self, tool_name: str) -> bool:
        """Enable a tool"""
        tool = self.get_tool(tool_name)
        if tool:
            tool.enabled = True
            logger.info(f"Enabled tool: {tool_name}")
            return True
        return False
    
    def disable_tool(self, tool_name: str) -> bool:
        """Disable a tool"""
        tool = self.get_tool(tool_name)
        if tool:
            tool.enabled = False
            logger.info(f"Disabled tool: {tool_name}")
            return True
        return False
    
    async def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name"""
        tool = self.get_tool(tool_name)
        
        if not tool:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool '{tool_name}' not found",
                tool_name=tool_name
            )
        
        if not tool.enabled:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool '{tool_name}' is disabled",
                tool_name=tool_name
            )
        
        return await tool.safe_execute(**kwargs)
    
    def get_schemas(self, category: Optional[ToolCategory] = None) -> List[Dict]:
        """Get tool schemas for function calling"""
        tools = self.list_tools(category, enabled_only=True)
        return [tool.get_schema() for tool in tools]
    
    def get_registry_info(self) -> Dict:
        """Get registry information"""
        info = {
            "total_tools": len(self._tools),
            "enabled_tools": len([t for t in self._tools.values() if t.enabled]),
            "categories": {}
        }
        
        for category in ToolCategory:
            category_tools = self._categories[category]
            enabled_count = len([
                name for name in category_tools 
                if name in self._tools and self._tools[name].enabled
            ])
            
            info["categories"][category.value] = {
                "total": len(category_tools),
                "enabled": enabled_count,
                "tools": list(category_tools)
            }
        
        return info

def create_default_registry() -> ToolRegistry:
    """Create a registry with default tools"""
    registry = ToolRegistry()
    
    # Import and register Kubernetes tools
    try:
        from .kubernetes.kubectl import KubectlTool
        from .kubernetes.logs import LogsTool
        
        registry.register(KubectlTool())
        registry.register(LogsTool())
        
    except ImportError as e:
        logger.warning(f"Could not import Kubernetes tools: {e}")
    
    # Import and register Istio tools
    try:
        from .istio.proxy import ProxyTool
        from .istio.config import ConfigTool
        
        registry.register(ProxyTool())
        registry.register(ConfigTool())
        
    except ImportError as e:
        logger.warning(f"Could not import Istio tools: {e}")
    
    return registry