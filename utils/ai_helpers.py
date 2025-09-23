import requests
import logging
import json
from io import BytesIO

logger = logging.getLogger(__name__)

class AIHelper:
    def __init__(self, openai_api_key=None, hf_api_key=None, base_url="https://openrouter.ai/api/v1"):
        self.openai_api_key = openai_api_key
        self.hf_api_key = hf_api_key
        self.base_url = base_url

    # ========== TEXT CHAT (OpenRouter) ==========
    def chat_reply(self, prompt, history=None, model="openai/gpt-3.5-turbo"):
        try:
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json"
            }

            # Agar history hai to usko add karo
            messages = []
            if history:
                for h in history:
                    messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": prompt})

            data = {
                "model": model,
                "messages": messages,
                "temperature": 0.8,
                "max_tokens": 500
            }

            logger.info(f"Sending prompt to OpenRouter model={model}: {prompt[:100]}...")

            resp = requests.post(url, headers=headers, json=data, timeout=30)
            resp.raise_for_status()
            j = resp.json()
            return j["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"OpenRouter error: {e}")
            return "⚠️ Sorry, AI se baat nahi ho paayi."

    # ========== IMAGE GENERATION (HuggingFace) ==========
    def generate_image(self, prompt, model="stabilityai/stable-diffusion-xl-base-1.0"):
        if not self.hf_api_key:
            return None, "⚠️ HuggingFace API key missing."

        try:
            url = f"https://api-inference.huggingface.co/models/{model}"
            headers = {
                "Authorization": f"Bearer {self.hf_api_key}",
                "Content-Type": "application/json"
            }
            payload = {"inputs": prompt}

            logger.info(f"HF request sent to {url} with prompt: {prompt}")

            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)

            if resp.status_code == 200:
                logger.info("HF image generation success ✅")
                return BytesIO(resp.content), None   # ab bot.send_photo ke liye ready hai
            else:
                logger.error(f"HF error {resp.status_code}: {resp.text}")
                return None, f"⚠️ HF error: {resp.status_code}"

        except Exception as e:
            logger.error(f"HF error: {e}")
            return None, f"⚠️ HF exception: {e}"
