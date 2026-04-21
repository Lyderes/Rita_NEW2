from __future__ import annotations

import httpx
import json
import logging
from typing import Any, Dict

from app.core.config import get_settings

logger = logging.getLogger(__name__)

class ClaudeClient:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.anthropic_api_key
        self.model = settings.anthropic_model
        self.timeout = settings.anthropic_timeout_seconds
        self.url = "https://api.anthropic.com/v1/messages"
        
    async def analyze_text(self, system_prompt: str, user_text: str) -> Dict[str, Any]:
        """Call Claude API with a system prompt and user text, expecting a JSON response."""
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not configured. Skipping AI analysis.")
            raise ValueError("Anthropic API key is missing")

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        data = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_text}
            ],
            # We will instruct Claude to return JSON in the system prompt.
            # Some versions support tools/json_mode but for MVP a clear prompt is enough.
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                
                # Extract text content from message structure
                content = result["content"][0]["text"]
                
                # Attempt to parse JSON from the text
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON from Claude response: {content}")
                    raise ValueError("Invalid JSON response from AI")
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"Claude API HTTP error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Error calling Claude API: {str(e)}")
                raise
