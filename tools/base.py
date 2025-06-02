"""
Base tool classes and interfaces
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from enum import Enum

logger = logging.getLogger(__name__)

class ToolCategory(Enum):
    """Categories of tools"""
    KUBERNETES = "kubernetes"
    ISTIO = "istio"
    OBSERVABILITY = "observability"
    NETWORKING = "networking"
    SECURITY = "security"

@dataclass
class ToolResult:
    """Result of tool execution"""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tool_name: Optional[str] = None
    execution_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
            "tool_name": self.tool_name,
            "execution_time": self.execution_time
        }

@dataclass
class ToolParameter:
    """Tool parameter definition"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum_values: Optional[List[str]] = None
    
    def to_schema(self) -> Dict[str, Any]:
        """Convert to JSON schema format"""
        schema = {
            "type": self.type,
            "description": self.description
        }
        
        if self.enum_values:
            schema["enum"] = self.enum_values
        
        if not self.required and self.default is not None:
            schema["default"] = self.default
            
        return schema

class Tool(ABC):
    """Abstract base class for all tools"""
    
    def __init__(
        self, 
        name: str, 
        description: str, 
        category: ToolCategory = ToolCategory.KUBERNETES
    ):
        self.name = name
        self.description = description
        self.category = category
        self.enabled = True
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters"""
        pass
    
    @abstractmethod
    def get_parameters(self) -> List[ToolParameter]:
        """Get list of tool parameters"""
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for function calling"""
        parameters = self.get_parameters()
        
        properties = {}
        required = []
        
        for param in parameters:
            properties[param.name] = param.to_schema()
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    
    def validate_parameters(self, **kwargs) -> Dict[str, str]:
        """Validate parameters and return errors"""
        errors = {}
        parameters = {p.name: p for p in self.get_parameters()}
        
        # Check required parameters
        for param_name, param in parameters.items():
            if param.required and param_name not in kwargs:
                errors[param_name] = f"Required parameter '{param_name}' is missing"
        
        # Check enum values
        for param_name, value in kwargs.items():
            if param_name in parameters:
                param = parameters[param_name]
                if param.enum_values and value not in param.enum_values:
                    errors[param_name] = f"Value '{value}' not in allowed values: {param.enum_values}"
        
        return errors
    
    async def safe_execute(self, **kwargs) -> ToolResult:
        """Execute tool with validation and error handling"""
        import time
        start_time = time.time()
        
        try:
            # Validate parameters
            validation_errors = self.validate_parameters(**kwargs)
            if validation_errors:
                error_msg = "; ".join([f"{k}: {v}" for k, v in validation_errors.items()])
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Parameter validation failed: {error_msg}",
                    tool_name=self.name,
                    execution_time=time.time() - start_time
                )
            
            # Execute the tool
            logger.debug(f"Executing tool {self.name} with parameters: {kwargs}")
            result = await self.execute(**kwargs)
            
            # Add metadata
            result.tool_name = self.name
            result.execution_time = time.time() - start_time
            
            logger.debug(f"Tool {self.name} completed in {result.execution_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Tool {self.name} failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                tool_name=self.name,
                execution_time=time.time() - start_time
            )

class AsyncTool(Tool):
    """Base class for asynchronous tools"""
    pass

class SyncTool(Tool):
    """Base class for synchronous tools that need async wrapper"""
    
    @abstractmethod
    def execute_sync(self, **kwargs) -> ToolResult:
        """Synchronous execution method"""
        pass
    
    async def execute(self, **kwargs) -> ToolResult:
        """Async wrapper for sync execution"""
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self.execute_sync, **kwargs
        )