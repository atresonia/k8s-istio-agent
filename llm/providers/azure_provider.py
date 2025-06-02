"""
Azure OpenAI Provider
"""
import logging
from typing import List, Dict, Any, Optional
import httpx

from ..provider import LLMProvider, Message, LLMResponse

logger = logging.getLogger(__name__)

class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI provider for enterprise Azure deployments"""
    
    def _setup(self):
        """Initialize Azure OpenAI client"""
        self.azure_endpoint = self.config.get("azure_endpoint")
        self.api_key = self.config.get("api_key")
        self.api_version = self.config.get("api_version", "2023-12-01-preview")
        self.deployment_name = self.config.get("deployment_name") or self.config.get("model", "gpt-4")
        
        if not self.azure_endpoint:
            raise ValueError("Azure OpenAI provider requires 'azure_endpoint'")
        
        if not self.api_key:
            raise ValueError("Azure OpenAI provider requires 'api_key'")
        
        # Ensure endpoint format is correct
        if not self.azure_endpoint.endswith('/'):
            self.azure_endpoint += '/'
        
        self.base_url = f"{self.azure_endpoint}openai/deployments/{self.deployment_name}"
        
        self.headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        logger.info(f"Initialized Azure OpenAI provider: {self.deployment_name}")
    
    async def chat_completion(
        self, 
        messages: List[Message], 
        **kwargs
    ) -> LLMResponse:
        """Generate chat completion using Azure OpenAI API"""
        try:
            # Convert messages to Azure OpenAI format
            azure_messages = [
                {"role": msg.role, "content": msg.content} 
                for msg in messages
            ]
            
            # Prepare request parameters
            payload = {
                "messages": azure_messages,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2048),
                "top_p": kwargs.get("top_p", 1.0),
                "frequency_penalty": kwargs.get("frequency_penalty", 0),
                "presence_penalty": kwargs.get("presence_penalty", 0),
                "stop": kwargs.get("stop", None)
            }
            
            # Add function calling if supported and provided
            if "functions" in kwargs:
                payload["functions"] = kwargs["functions"]
            if "function_call" in kwargs:
                payload["function_call"] = kwargs["function_call"]
            
            url = f"{self.base_url}/chat/completions?api-version={self.api_version}"
            
            logger.debug(f"Making Azure OpenAI request to: {url}")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Extract response
                if "choices" not in data or not data["choices"]:
                    raise ValueError(f"No choices in Azure OpenAI response: {data}")
                
                choice = data["choices"][0]
                message = choice["message"]
                content = message.get("content", "")
                
                # Handle function calls
                if message.get("function_call"):
                    func_call = message["function_call"]
                    content = f"Function call: {func_call['name']}({func_call['arguments']})"
                
                usage = data.get("usage", {})
                
                return LLMResponse(
                    content=content,
                    model=self.deployment_name,
                    usage=usage,
                    metadata={
                        "provider": "azure_openai",
                        "deployment": self.deployment_name,
                        "api_version": self.api_version,
                        "finish_reason": choice.get("finish_reason")
                    }
                )
                
        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = error_data.get("error", {}).get("message", str(e))
            except:
                error_detail = str(e)
            
            logger.error(f"Azure OpenAI API error: {e.response.status_code} - {error_detail}")
            raise RuntimeError(f"Azure OpenAI API error: {error_detail}")
        except Exception as e:
            logger.error(f"Azure OpenAI error: {e}")
            raise RuntimeError(f"Failed to get response from Azure OpenAI: {e}")
    
    def supports_function_calling(self) -> bool:
        """Azure OpenAI supports function calling for compatible deployments"""
        return True
    
    def supports_streaming(self) -> bool:
        """Azure OpenAI supports streaming"""
        return True
    
    async def stream_completion(
        self, 
        messages: List[Message], 
        **kwargs
    ):
        """Stream chat completion"""
        try:
            azure_messages = [
                {"role": msg.role, "content": msg.content} 
                for msg in messages
            ]
            
            payload = {
                "messages": azure_messages,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2048),
                "stream": True
            }
            
            url = f"{self.base_url}/chat/completions?api-version={self.api_version}"
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    url,
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
                                import json
                                data = json.loads(data_str)
                                if "choices" in data and data["choices"]:
                                    delta = data["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        yield delta["content"]
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            logger.error(f"Azure OpenAI streaming error: {e}")
            raise RuntimeError(f"Failed to stream from Azure OpenAI: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        info = super().get_model_info()
        info.update({
            "deployment_name": self.deployment_name,
            "azure_endpoint": self.azure_endpoint,
            "api_version": self.api_version,
            "region": self._extract_region_from_endpoint()
        })
        return info
    
    def _extract_region_from_endpoint(self) -> str:
        """Extract Azure region from endpoint URL"""
        try:
            # Extract region from URLs like https://myresource.openai.azure.com/
            import re
            match = re.search(r'https://([^.]+)\.openai\.azure\.com', self.azure_endpoint)
            return match.group(1) if match else "unknown"
        except:
            return "unknown"