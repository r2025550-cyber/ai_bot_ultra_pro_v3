import os
import logging
import requests
from io import BytesIO

class AIHelper:
    def __init__(self, openai_api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        """
        Helper class for AI text + image generation
        """
        self.api_key = openai_api_key
        self.base_url = base_url
        self.logger = logging.getLogger(__name__)

        # Hugging Face API key (for image generation)
        self.hf_token = os.getenv("HUGGINGFACE_API_KEY")
        if not self.hf_token:
            self.logger.warning("HUGGINGFACE_API_KEY not set. Image generation will not work.")

    # ================= TEXT REPLY (OpenRouter / OpenAI) ==================
    def chat_reply(self, prompt: str, memory: list = None, model: str = "openai/gpt-3.5-turbo"):
        """
        Calls OpenRouter (or OpenAI-compatible) API for text chat completion.
        :param prompt: User input + persona prompt
        :param memory: List of dicts [{"role": "user/assistant", "content": "..."}]
        :param model: Model name (default GPT-3.5-turbo via OpenRouter)
        """
        if not self.api_key:
            raise ValueError("API key not configured for text model")

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        messages = []

        # Add history
        if memory:
            for m in memory:
                messages.append({"role": m["role"], "content": m["content"]})

        # Add new user prompt
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": 500,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            self.logger.error(f"Text generation error: {e}")
            return "⚠️ Sorry, abhi reply nahi de pa rahi 💖"

    # ================= IMAGE GENERATION (Hugging Face) ==================
    def generate_image(self, prompt: str, model: str = "runwayml/stable-diffusion-v1-5"):
        """
        Calls Hugging Face Inference API for Stable Diffusion models.
        Returns a BytesIO image or None if failed.
        """
        if not self.hf_token:
            self.logger.error("HUGGINGFACE_API_KEY not configured")
            return None

        url = f"https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0"
        headers = {"Authorization": f"Bearer {self.hf_token}"}
        payload = {
            "inputs": prompt,
            "options": {"wait_for_model": True}
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            if resp.status_code == 200:
                return BytesIO(resp.content)
            else:
                self.logger.error("HF error %s: %s", resp.status_code, resp.text)
                return None
        except Exception as e:
            self.logger.error("HF request failed: %s", e)
            return None
