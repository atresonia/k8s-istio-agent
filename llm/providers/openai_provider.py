"""
OpenAI LLM Provider
"""
import logging
from typing import List, Dict, Any, Optional
import openai
from openai import AsyncOpenAI

from ..provider import LLMProvider, Message, LLMResponse

logger = logging.getLogger(__name__)

class OpenAIProvider(LLMProvider):
    """OpenAI provider for GPT models"""
    
    def _setup(self):
        """Initialize OpenAI client"""
        self.api_key = self.config.get("api_key")
        self.model = self.config.get("model", "gpt-4")
        self.base_url = self.config.get("base_url", "https://api.openai.com/v1")
        self.organization = self.config.get("organization")
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            organization=self.organization
        )
        
        logger.info(f"Initialized OpenAI provider with model: {self.model}")
    
    async def chat_completion(
        self, 
        messages: List[Message], 
        **kwargs
    ) -> LLMResponse:
        """Generate chat completion using OpenAI API"""
        try:
            # Convert messages to OpenAI format
            openai_messages = [
                {"role": msg.role, "content": msg.content} 
                for msg in messages
            ]
            
            # Prepare request parameters
            request_params = {
                "model": kwargs.get("model", self.model),
                "messages": openai_messages,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2048),
                "top_p": kwargs.get("top_p", 1.0),
                "frequency_penalty": kwargs.get("frequency_penalty", 0),
                "presence_penalty": kwargs.get("presence_penalty", 0)
            }
            
            # Add function calling if supported and provided
            if "functions" in kwargs:
                request_params["functions"] = kwargs["functions"]
            if "function_call" in kwargs:
                request_params["function_call"] = kwargs["function_call"]
            
            logger.debug(f"Making OpenAI API request with {len(openai_messages)} messages")
            
            response = await self.client.chat.completions.create(**request_params)
            
            # Extract response
            message = response.choices[0].message
            content = message.content or ""
            
            # Handle function calls
            if hasattr(message, 'function_call') and message.function_call:
                content = f"Function call: {message.function_call.name}({message.function_call.arguments})"
            
            usage = None
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            
            return LLMResponse(
                content=content,
                model=response.model,
                usage=usage,
                metadata={
                    "provider": "openai",
                    "finish_reason": response.choices[0].finish_reason
                }
            )
            
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise RuntimeError(f"OpenAI API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise RuntimeError(f"Failed to generate completion: {e}")
    
    def supports_function_calling(self) -> bool:
        """OpenAI GPT-3.5-turbo and GPT-4 support function calling"""
        return "gpt-3.5-turbo" in self.model or "gpt-4" in self.model
    
    def supports_streaming(self) -> bool:
        """OpenAI supports streaming"""
        return True
    
    async def stream_completion(
        self, 
        messages: List[Message], 
        **kwargs
    ):
        """Stream chat completion (generator)"""
        try:
            openai_messages = [
                {"role": msg.role, "content": msg.content} 
                for msg in messages
            ]
            
            request_params = {
                "model": kwargs.get("model", self.model),
                "messages": openai_messages,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2048),
                "stream": True
            }
            
            async for chunk in await self.client.chat.completions.create(**request_params):
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise RuntimeError(f"Failed to stream completion: {e}")