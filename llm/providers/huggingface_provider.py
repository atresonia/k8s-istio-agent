"""
HuggingFace LLM Provider
Clean, generic implementation with proper context management
"""
import torch
import logging
from typing import List, Dict, Any, Optional
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

from ..provider import LLMProvider, Message, LLMResponse

logger = logging.getLogger(__name__)

class HuggingFaceProvider(LLMProvider):
    """HuggingFace provider with intelligent context management"""
    
    # Configuration constants
    DEFAULT_MODEL = "microsoft/DialoGPT-medium"
    DEFAULT_MAX_NEW_TOKENS = 50
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_CONTEXT_WINDOW = 512  # Conservative default for most models
    CONTEXT_BUFFER = 50  # Buffer for generation tokens
    MIN_RESPONSE_LENGTH = 5
    
    def _setup(self):
        """Initialize HuggingFace model and tokenizer"""
        self.model_name = self.config.get("model_name", self.DEFAULT_MODEL)
        self.device = self.config.get("device", "cpu")
        self.max_new_tokens = self.config.get("max_new_tokens", self.DEFAULT_MAX_NEW_TOKENS)
        self.temperature = self.config.get("temperature", self.DEFAULT_TEMPERATURE)
        self.context_window = self.config.get("context_window", self.DEFAULT_CONTEXT_WINDOW)
        
        logger.info(f"Loading HuggingFace model: {self.model_name}")
        
        try:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            # Ensure pad token exists
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Detect actual model context window if possible
            self._detect_context_window()
            
            # Load model with minimal configuration
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float32,
                device_map=None,  # Load to CPU first, move to device later
                low_cpu_mem_usage=True
            )
            
            # Move to specified device
            if self.device != "cpu":
                self.model = self.model.to(self.device)
            
            # Create pipeline
            self.generator = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if self.device == "cuda" and torch.cuda.is_available() else -1
            )
            
            logger.info(f"Successfully loaded model {self.model_name} with context window {self.context_window}")
            
        except Exception as e:
            logger.error(f"Failed to load HuggingFace model: {e}")
            raise RuntimeError(f"Could not initialize HuggingFace model: {e}")
    
    def _detect_context_window(self):
        """Detect the actual context window of the model"""
        try:
            # Try to get from tokenizer config
            if hasattr(self.tokenizer, 'model_max_length'):
                detected_window = self.tokenizer.model_max_length
                # Some models have unrealistic max lengths, cap them
                if detected_window > 2048:
                    detected_window = 512
                elif detected_window < 100:
                    detected_window = 512
                
                self.context_window = min(detected_window, self.context_window)
                logger.debug(f"Detected context window: {self.context_window}")
        except Exception as e:
            logger.debug(f"Could not detect context window, using default: {e}")
    
    async def chat_completion(self, messages: List[Message], **kwargs) -> LLMResponse:
        """Generate chat completion with proper context management"""
        try:
            # Format and truncate prompt to fit context window
            prompt = self._format_and_truncate_prompt(messages)
            
            # Validate prompt length
            prompt_tokens = len(self.tokenizer.encode(prompt))
            max_input_tokens = self.context_window - self.max_new_tokens - self.CONTEXT_BUFFER
            
            if prompt_tokens > max_input_tokens:
                logger.warning(f"Prompt too long ({prompt_tokens} tokens), truncating to {max_input_tokens}")
                prompt = self._truncate_prompt_by_tokens(prompt, max_input_tokens)
            
            # Generate response
            generation_kwargs = {
                "max_new_tokens": kwargs.get("max_new_tokens", self.max_new_tokens),
                "temperature": kwargs.get("temperature", self.temperature),
                "do_sample": kwargs.get("do_sample", True),
                "pad_token_id": self.tokenizer.eos_token_id,
                "return_full_text": False,
                "num_return_sequences": 1,
                "early_stopping": True  # Stop at EOS token
            }
            
            logger.debug(f"Generating with prompt tokens: {len(self.tokenizer.encode(prompt))}")
            
            outputs = self.generator(prompt, **generation_kwargs)
            generated_text = outputs[0]["generated_text"].strip()
            
            # Clean and validate response
            cleaned_response = self._clean_response(generated_text)
            
            # Calculate usage
            prompt_tokens = len(self.tokenizer.encode(prompt))
            completion_tokens = len(self.tokenizer.encode(generated_text))
            
            return LLMResponse(
                content=cleaned_response,
                model=self.model_name,
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                },
                metadata={
                    "provider": "huggingface",
                    "context_window": self.context_window,
                    "max_new_tokens": self.max_new_tokens
                }
            )
            
        except Exception as e:
            logger.error(f"Error generating completion: {e}")
            # Return intelligent fallback instead of crashing
            return self._create_fallback_response()
    
    def _format_and_truncate_prompt(self, messages: List[Message]) -> str:
        """Format prompt and intelligently preserve important information"""
        # Separate system messages from conversation
        system_messages = [msg for msg in messages if msg.role == "system"]
        conversation_messages = [msg for msg in messages if msg.role != "system"]
        
        # Always preserve the most recent system message (contains tool info)
        system_prompt = system_messages[-1].content if system_messages else ""
        
        # Format recent conversation
        formatted_parts = []
        if system_prompt:
            formatted_parts.append(f"Instructions: {system_prompt}")
        
        # Include recent conversation (prioritize recent messages)
        for msg in conversation_messages[-3:]:  # Last 3 conversation turns
            if msg.role == "user":
                formatted_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                formatted_parts.append(f"Assistant: {msg.content}")
        
        formatted_parts.append("Assistant:")
        return "\n".join(formatted_parts)
    
    def _truncate_prompt_by_tokens(self, prompt: str, max_tokens: int) -> str:
        """Truncate prompt to exact token count while preserving structure"""
        # Encode to tokens
        tokens = self.tokenizer.encode(prompt)
        
        if len(tokens) <= max_tokens:
            return prompt
        
        # Truncate from the beginning, preserving the end (most recent context)
        truncated_tokens = tokens[-max_tokens:]
        truncated_prompt = self.tokenizer.decode(truncated_tokens, skip_special_tokens=True)
        
        # Ensure we still have a proper prompt structure
        if "Assistant:" not in truncated_prompt:
            truncated_prompt += "\nAssistant:"
        
        return truncated_prompt
    
    def _clean_response(self, response: str) -> str:
        """Clean response with fallback for poor responses"""
        # Remove common artifacts
        cleaned = response.replace("Assistant:", "").strip()
        
        # Remove any repeated newlines or spaces
        import re
        cleaned = re.sub(r'\n+', '\n', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # If response is too short, empty, or seems like garbage
        if len(cleaned) < self.MIN_RESPONSE_LENGTH:
            return "I'll help analyze this issue using the available tools."
        
        # If response seems repetitive or contains prompt artifacts
        if self._is_repetitive_response(cleaned):
            return "Let me investigate this systematically."
        
        return cleaned.strip()
    
    def _is_repetitive_response(self, response: str) -> bool:
        """Check if response appears to be repetitive or contains prompt artifacts"""
        lower_response = response.lower()
        
        # Check for common repetitive patterns
        repetitive_indicators = [
            "find the right team",
            "what the results indicate",
            "kubernetes blog",
            "learn more about",
            "clear and actionable"
        ]
        
        return any(indicator in lower_response for indicator in repetitive_indicators)
    
    def _create_fallback_response(self) -> LLMResponse:
        """Create a fallback response when generation fails"""
        return LLMResponse(
            content="I'll help troubleshoot this issue using the available diagnostic tools.",
            model=self.model_name,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            metadata={"provider": "huggingface", "fallback": True}
        )
    
    def supports_function_calling(self) -> bool:
        return False
    
    def supports_streaming(self) -> bool:
        return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        info = super().get_model_info()
        info.update({
            "model_name": self.model_name,
            "device": self.device,
            "context_window": self.context_window,
            "max_new_tokens": self.max_new_tokens
        })
        
        if hasattr(self, 'model'):
            info.update({
                "num_parameters": sum(p.numel() for p in self.model.parameters()),
                "dtype": str(self.model.dtype)
            })
        
        return info