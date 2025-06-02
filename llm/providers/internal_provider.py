"""
Internal LLM Provider for enterprise LangChain wrappers
"""
import logging
from typing import List, Dict, Any, Optional
import httpx
import json

from ..provider import LLMProvider, Message, LLMResponse

logger = logging.getLogger(__name__)

class InternalProvider(LLMProvider):
    """Provider for internal enterprise LLM endpoints"""
    
    def _setup(self):
        """Initialize internal provider"""
        self.endpoint = self.config.get("endpoint")
        self.api_key = self.config.get("api_key")
        self.model = self.config.get("model", "internal-model")
        self.timeout = self.config.get("timeout", 60.0)
        
        if not self.endpoint:
            raise ValueError("Internal provider requires 'endpoint' configuration")
        
        if not self.api_key:
            raise ValueError("Internal provider requires 'api_key' configuration")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "k8s-istio-agent/1.0"
        }
        
        # Additional headers if specified
        extra_headers = self.config.get("headers", {})
        self.headers.update(extra_headers)
        
        logger.info(f"Initialized internal provider: {self.endpoint}")
    
    async def chat_completion(
        self, 
        messages: List[Message], 
        **kwargs
    ) -> LLMResponse:
        """Generate chat completion using internal API"""
        try:
            # Prepare request payload
            payload = {
                "messages": [
                    {"role": msg.role, "content": msg.content} 
                    for msg in messages
                ],
                "model": kwargs.get("model", self.model),
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2048),
                "top_p": kwargs.get("top_p", 1.0),
                "frequency_penalty": kwargs.get("frequency_penalty", 0),
                "presence_penalty": kwargs.get("presence_penalty", 0)
            }
            
            # Add any additional parameters from config
            extra_params = self.config.get("default_parameters", {})
            payload.update(extra_params)
            
            logger.debug(f"Making request to internal API: {self.endpoint}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.endpoint.rstrip('/')}/chat/completions",
                    headers=self.headers,
                    json=payload
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Extract response based on API format
                if "choices" in data and data["choices"]:
                    content = data["choices"][0]["message"]["content"]
                    model_used = data.get("model", self.model)
                    
                    usage = data.get("usage", {})
                    
                    return LLMResponse(
                        content=content,
                        model=model_used,
                        usage=usage,
                        metadata={
                            "provider": "internal",
                            "endpoint": self.endpoint,
                            "response_time": response.elapsed.total_seconds()
                        }
                    )
                else:
                    raise ValueError(f"Unexpected response format: {data}")
                    
        except httpx.TimeoutException:
            logger.error("Internal API request timed out")
            raise RuntimeError("Internal LLM API request timed out")
        except httpx.HTTPStatusError as e:
            logger.error(f"Internal API HTTP error: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"Internal LLM API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Internal API error: {e}")
            raise RuntimeError(f"Failed to get response from internal LLM: {e}")
    
    def supports_function_calling(self) -> bool:
        """Check if internal API supports function calling"""
        return self.config.get("supports_functions", False)
    
    def supports_streaming(self) -> bool:
        """Check if internal API supports streaming"""
        return self.config.get("supports_streaming", False)
    
    async def stream_completion(
        self, 
        messages: List[Message], 
        **kwargs
    ):
        """Stream completion if supported"""
        if not self.supports_streaming():
            raise NotImplementedError("Streaming not supported by this internal provider")
        
        payload = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "model": kwargs.get("model", self.model),
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
            "stream": True
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.endpoint.rstrip('/')}/chat/completions",
                headers=self.headers,
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and data["choices"]:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            continue

class LangChainProvider(InternalProvider):
    """Specialized provider for LangChain-based internal APIs"""
    
    def _setup(self):
        """Initialize LangChain provider with specific configurations"""
        super()._setup()
        
        # LangChain-specific configurations
        self.chain_type = self.config.get("chain_type", "conversation")
        self.memory_type = self.config.get("memory_type", "buffer")
        
        # Override endpoint path for LangChain APIs
        self.langchain_endpoint = f"{self.endpoint.rstrip('/')}/langchain/chat"
        
        logger.info(f"Initialized LangChain provider: {self.langchain_endpoint}")
    
    async def chat_completion(
        self, 
        messages: List[Message], 
        **kwargs
    ) -> LLMResponse:
        """Generate completion using LangChain API format"""
        try:
            # Convert messages to LangChain format
            langchain_messages = []
            for msg in messages:
                if msg.role == "system":
                    langchain_messages.append({"type": "system", "content": msg.content})
                elif msg.role == "user":
                    langchain_messages.append({"type": "human", "content": msg.content})
                elif msg.role == "assistant":
                    langchain_messages.append({"type": "ai", "content": msg.content})
            
            payload = {
                "messages": langchain_messages,
                "chain_type": self.chain_type,
                "memory_type": self.memory_type,
                "model_kwargs": {
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 2048)
                }
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.langchain_endpoint,
                    headers=self.headers,
                    json=payload
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Extract response from LangChain format
                content = data.get("response", "") or data.get("output", "")
                
                return LLMResponse(
                    content=content,
                    model=self.model,
                    usage=data.get("usage", {}),
                    metadata={
                        "provider": "langchain",
                        "chain_type": self.chain_type,
                        "endpoint": self.langchain_endpoint
                    }
                )
                
        except Exception as e:
            logger.error(f"LangChain API error: {e}")
            raise RuntimeError(f"Failed to get response from LangChain API: {e}")

# Example configurations for different internal setups

INTERNAL_CONFIG_EXAMPLES = {
    "basic_internal": {
        "endpoint": "https://internal-llm.company.com/api/v1",
        "api_key": "${INTERNAL_API_KEY}",
        "model": "company-gpt-4",
        "timeout": 60.0,
        "supports_functions": True,
        "supports_streaming": True
    },
    
    "langchain_wrapper": {
        "endpoint": "https://langchain-api.company.com",
        "api_key": "${LANGCHAIN_API_KEY}",
        "model": "langchain-gpt",
        "chain_type": "conversation",
        "memory_type": "buffer",
        "timeout": 90.0,
        "default_parameters": {
            "return_source_documents": False,
            "verbose": False
        }
    },
    
    "azure_internal": {
        "endpoint": "https://company-openai.openai.azure.com",
        "api_key": "${AZURE_INTERNAL_KEY}",
        "model": "gpt-4-company",
        "headers": {
            "api-version": "2023-12-01-preview",
            "Content-Type": "application/json"
        },
        "supports_functions": True
    }
}