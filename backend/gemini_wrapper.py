import os
import time
import logging
import google.generativeai as genai
from typing import List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("gemini_wrapper")

class GeminiWrapper:
    def __init__(self):
        self._available_models: List[str] = []
        self._last_cache_time: float = 0
        self._cache_ttl: int = 600  # 10 minutes cache
        self._is_configured = False

    def _configure(self, api_key: str):
        """Configure the SDK with the provided API key."""
        genai.configure(api_key=api_key)
        self._is_configured = True

    def _refresh_model_cache(self) -> None:
        """Fetch and cache available models that support content generation."""
        now = time.time()
        if now - self._last_cache_time < self._cache_ttl and self._available_models:
            return

        try:
            logger.info("Refreshing Gemini model cache...")
            models = genai.list_models()
            self._available_models = [
                m.name for m in models 
                if "generateContent" in m.supported_generation_methods
            ]
            self._last_cache_time = now
            logger.info(f"Available Gemini Models: {self._available_models}")
        except Exception as e:
            logger.error(f"Failed to fetch Gemini models: {e}")
            if not self._available_models:
                # Default to common models if listing fails
                self._available_models = ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]

    def select_best_model(self) -> str:
        """Selects the best available model based on priority list."""
        self._refresh_model_cache()
        
        priority_order = [
            "gemini-2.0-flash", 
            "gemini-2.0-flash-exp"
        ]

        for preferred in priority_order:
            for available in self._available_models:
                if preferred in available:
                    return available

        return "models/gemini-1.5-flash"

    def generate(self, api_key: str, prompt: str) -> str:
        """Generates content with automatic model selection and fallback."""
        self._configure(api_key)
        selected_model = self.select_best_model()
        logger.info(f"Generating content using model: {selected_model}")
        
        try:
            model = genai.GenerativeModel(selected_model)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error with model {selected_model}: {e}")
            
            # Smart Fallback
            fallback_model = "models/gemini-1.5-flash"
            logger.info(f"Attempting fallback to: {fallback_model}")
            try:
                model = genai.GenerativeModel(fallback_model)
                response = model.generate_content(fallback_model) # Trigger check
                response = model.generate_content(prompt)
                return response.text
            except Exception as fe:
                logger.critical(f"All Gemini models failed: {fe}")
                raise RuntimeError(f"Gemini generation failed: {fe}")

# Singleton
_wrapper = GeminiWrapper()

def generate_with_gemini(api_key: str, prompt: str) -> str:
    return _wrapper.generate(api_key, prompt)
