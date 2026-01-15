import json
import asyncio
from typing import Any, Dict, Optional, Type
from zhipuai import ZhipuAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings
from app.core.logging import get_logger
from pydantic import BaseModel

logger = get_logger("llm_client")

class LLMClient:
    def __init__(self):
        self.client = ZhipuAI(api_key=settings.LLM_API_KEY)
        self.model = settings.LLM_MODEL
        self.total_tokens = 0
        
    def _clean_json_string(self, content: str) -> str:
        """
        Clean the content string to extract valid JSON.
        Handles markdown code blocks (```json ... ```) and python code blocks (```python ... ```).
        Also attempts to extract list [ ... ] if expecting list.
        """
        content = content.strip()
        
        # Remove markdown code blocks
        if content.startswith("```"):
            # Find first newline
            newline_idx = content.find("\n")
            if newline_idx != -1:
                # Remove first line (```json or ```python)
                content = content[newline_idx+1:]
            
            # Remove last ``` if present
            if content.endswith("```"):
                content = content[:-3]
        
        content = content.strip()
        
        # Find the first '{' or '['
        first_curly = content.find("{")
        first_square = content.find("[")
        
        start = -1
        end = -1
        
        # Determine if we are looking for object or list
        # If both exist, take the earlier one
        if first_curly != -1 and first_square != -1:
            if first_curly < first_square:
                start = first_curly
                end = content.rfind("}")
            else:
                start = first_square
                end = content.rfind("]")
        elif first_curly != -1:
            start = first_curly
            end = content.rfind("}")
        elif first_square != -1:
            start = first_square
            end = content.rfind("]")
            
        if start != -1 and end != -1:
            return content[start:end+1]
        
        return content

    @retry(
        stop=stop_after_attempt(settings.LLM_MAX_RETRIES + 1),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception), # Broad for now, can refine
        reraise=True
    )
    def chat_completion(
        self, 
        messages: list, 
        response_format: Optional[Type[BaseModel]] = None,
        temperature: float = settings.LLM_TEMPERATURE
    ) -> Dict[str, Any]:
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": settings.LLM_MAX_TOKENS,
            }
            
            # logger.debug(f"Calling LLM with messages: {messages}")
            response = self.client.chat.completions.create(**kwargs)
            
            # Track tokens
            if hasattr(response, 'usage') and response.usage:
                self.total_tokens += response.usage.total_tokens
                
            content = response.choices[0].message.content
            
            if response_format:
                try:
                    json_str = self._clean_json_string(content)
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON: {content}")
                    raise e
            
            return content

        except Exception as e:
            logger.error(f"LLM Call failed: {e}")
            raise e

    async def achat_completion(
        self, 
        messages: list, 
        response_format: Optional[Type[BaseModel]] = None,
        temperature: float = settings.LLM_TEMPERATURE
    ) -> Dict[str, Any]:
        """Async wrapper for chat_completion using asyncio.to_thread"""
        return await asyncio.to_thread(
            self.chat_completion, 
            messages=messages, 
            response_format=response_format, 
            temperature=temperature
        )

llm_client = LLMClient()
