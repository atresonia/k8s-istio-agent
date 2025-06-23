"""
Ollama LLM Provider
"""
import logging
from typing import List, Dict, Any, Optional
import httpx
import json

from ..provider import LLMProvider, Message, LLMResponse

logger = logging.getLogger(__name__)

class OllamaProvider(LLMProvider):
    """Provider for Ollama models running locally"""
    
    def _setup(self):
        """Initialize Ollama provider"""
        self.base_url = self.config.get("base_url", "http://localhost:11434")
        self.model = self.config.get("model", "llama2")
        self.timeout = self.config.get("timeout", 60.0)
        
        # Ensure base URL format is correct
        if not self.base_url.endswith('/'):
            self.base_url += '/'
        
        logger.info(f"Initialized Ollama provider with model: {self.model}")
    
    async def chat_completion(
        self, 
        messages: List[Message], 
        **kwargs
    ) -> LLMResponse:
        """Generate chat completion using Ollama API"""
        try:
            # Convert messages to Ollama format
            ollama_messages = [
                {"role": msg.role, "content": msg.content} 
                for msg in messages
            ]
            
            # Prepare request parameters
            payload = {
                "model": kwargs.get("model", self.model),
                "messages": ollama_messages,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", 0.7),
                    "num_predict": kwargs.get("max_tokens", 2048),
                    "top_p": kwargs.get("top_p", 1.0),
                    "repeat_penalty": kwargs.get("frequency_penalty", 1.1),
                    "stop": kwargs.get("stop", None)
                }
            }
            
            url = f"{self.base_url}api/chat"
            
            logger.debug(f"Making Ollama request to: {url}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Extract response
                if "message" not in data:
                    raise ValueError(f"Unexpected Ollama response format: {data}")
                
                content = data["message"]["content"]
                
                # Calculate usage (Ollama doesn't provide token counts)
                usage = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
                
                return LLMResponse(
                    content=content,
                    model=self.model,
                    usage=usage,
                    metadata={
                        "provider": "ollama",
                        "model": self.model,
                        "response_time": response.elapsed.total_seconds()
                    }
                )
                
        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = error_data.get("error", str(e))
            except:
                error_detail = str(e)
            
            logger.error(f"Ollama API error: {e.response.status_code} - {error_detail}")
            raise RuntimeError(f"Ollama API error: {error_detail}")
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise RuntimeError(f"Failed to get response from Ollama: {e}")
    
    def supports_function_calling(self) -> bool:
        """Ollama doesn't support function calling"""
        return False
    
    def supports_streaming(self) -> bool:
        """Ollama supports streaming"""
        return True
    
    async def stream_completion(
        self, 
        messages: List[Message], 
        **kwargs
    ):
        """Stream chat completion"""
        try:
            ollama_messages = [
                {"role": msg.role, "content": msg.content} 
                for msg in messages
            ]
            
            payload = {
                "model": kwargs.get("model", self.model),
                "messages": ollama_messages,
                "stream": True,
                "options": {
                    "temperature": kwargs.get("temperature", 0.7),
                    "num_predict": kwargs.get("max_tokens", 2048),
                    "top_p": kwargs.get("top_p", 1.0),
                    "repeat_penalty": kwargs.get("frequency_penalty", 1.1)
                }
            }
            
            url = f"{self.base_url}api/chat"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                data = json.loads(line)
                                if "message" in data and "content" in data["message"]:
                                    yield data["message"]["content"]
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            logger.error(f"Ollama streaming error: {e}")
            raise RuntimeError(f"Failed to stream from Ollama: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        info = super().get_model_info()
        info.update({
            "model": self.model,
            "base_url": self.base_url
        })
        return info
