import logging
import requests

class AIHelper:
    def __init__(self, openai_api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = openai_api_key
        self.base_url = base_url
        self.logger = logging.getLogger(__name__)

    def chat_reply(self, prompt: str, memory: list = None) -> str:
        """
        Generate a roleplay chat reply using memory + persona.
        memory = list of dicts like: [{"role":"user","content":"..."}, {"role":"assistant","content":"..."}]
        """
        if memory is None:
            memory = []

        # Persona (always injected)
        persona = {
            "role": "system",
            "content": (
                "Tum ek ladki ho jiska naam 'Butki' hai 💖\n"
                "Butki funny, thodi naughty aur friendly hai 😘\n"
                "Har reply roleplay style me ho, emojis ke sath 💅✨\n"
                "Group me sabko apna dost samjho 🥳 aur mazaak karte hue baat karo.\n"
                "Private chat me thoda cute aur close behave karo 💕\n"
                "Hamesha ladki wali style, emojis, aur thoda masti bhara tone rakho 💖\n"
            )
        }

        # Combine persona + memory + new prompt
        messages = [persona]
        for m in memory:
            if isinstance(m, dict) and "role" in m and "content" in m:
                messages.append(m)
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://t.me/ButkiBot",
            "X-Title": "Butki AI Bot"
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={
                    "model": "gpt-4o-mini",   # OpenRouter free/fast model
                    "messages": messages,
                    "temperature": 0.9
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                self.logger.error(f"AI API Error: {response.status_code} {response.text}")
                return "⚠️ Sorry, abhi thoda busy hoon 💖"

        except Exception as e:
            self.logger.error(f"AI request failed: {e}")
            return "⚠️ Sorry, abhi thoda busy hoon 💖"
