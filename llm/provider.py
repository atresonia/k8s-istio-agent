"""
LLM Provider abstraction layer
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

@dataclass
class Message:
    role: str  # 'system', 'user', 'assistant'
    content: str

@dataclass
class LLMResponse:
    content: str
    model: str
    usage: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

class LLMProvider(ABC):
    """Abstract base class for all LLM providers"""
    
    def __init__(self, **config):
        self.config = config
        self._setup()
    
    @abstractmethod
    def _setup(self):
        """Initialize the provider with configuration"""
        pass
    
    @abstractmethod
    async def chat_completion(
        self, 
        messages: List[Message], 
        **kwargs
    ) -> LLMResponse:
        """Generate a chat completion response"""
        pass
    
    @abstractmethod
    def supports_function_calling(self) -> bool:
        """Whether this provider supports function calling"""
        pass
    
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether this provider supports streaming responses"""
        pass
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the model"""
        return {
            "provider": self.__class__.__name__,
            "model": getattr(self, 'model_name', 'unknown'),
            "supports_function_calling": self.supports_function_calling(),
            "supports_streaming": self.supports_streaming()
        }

class LLMFactory:
    """Factory for creating LLM providers"""
    
    _providers: Dict[str, type] = {}
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """Register a new LLM provider"""
        cls._providers[name] = provider_class
        logger.info(f"Registered LLM provider: {name}")
    
    @classmethod
    def create_provider(cls, provider_name: str, **config) -> LLMProvider:
        """Create an LLM provider instance"""
        if provider_name not in cls._providers:
            available = list(cls._providers.keys())
            raise ValueError(
                f"Unknown provider: {provider_name}. "
                f"Available providers: {available}"
            )
        
        provider_class = cls._providers[provider_name]
        return provider_class(**config)
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """List all registered providers"""
        return list(cls._providers.keys())

# Auto-register providers when imported
def _auto_register_providers():
    """Automatically register all available providers"""
    try:
        from .providers.openai_provider import OpenAIProvider
        LLMFactory.register_provider("openai", OpenAIProvider)
    except ImportError:
        logger.warning("OpenAI provider not available")
    
    try:
        from .providers.huggingface_provider import HuggingFaceProvider
        LLMFactory.register_provider("huggingface", HuggingFaceProvider)
    except ImportError:
        logger.warning("HuggingFace provider not available")
    
    try:
        from .providers.azure_provider import AzureOpenAIProvider
        LLMFactory.register_provider("azure", AzureOpenAIProvider)
    except ImportError:
        logger.warning("Azure OpenAI provider not available")
    
    try:
        from .providers.internal_provider import InternalProvider
        LLMFactory.register_provider("internal", InternalProvider)
    except ImportError:
        logger.warning("Internal provider not available")
    
    try:
        from .providers.ollama_provider import OllamaProvider
        LLMFactory.register_provider("ollama", OllamaProvider)
    except ImportError:
        logger.warning("Ollama provider not available")

# Register providers on module import
_auto_register_providers()