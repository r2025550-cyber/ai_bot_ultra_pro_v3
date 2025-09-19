# utils/ai_helpers.py

from openai import OpenAI

class AIHelper:
    def __init__(self, openai_api_key: str):
        if not openai_api_key or not openai_api_key.startswith("sk-"):
            raise ValueError("❌ OPENAI_API_KEY is missing or invalid!")
        self.client = OpenAI(api_key=openai_api_key)

    def chat_reply(self, user_text: str, memory=[]):
        """
        Generate a reply from AI model with short conversation memory.
        """
        try:
            messages = [{"role": "system", "content": "You are a helpful Telegram AI bot."}]
            for role, content in memory:
                messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": user_text})

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",   # Lightweight fast model
                messages=messages,
                max_tokens=300
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            print("AI ERROR (chat):", e)
            return "⚠️ AI error, please try again later."

    def vision_describe(self, image_url: str):
        """
        Describe an image using GPT-4o-mini vision.
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an image analysis assistant."},
                    {"role": "user", "content": [
                        {"type": "text", "text": "Describe this image in detail."},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]}
                ],
                max_tokens=200
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            print("AI ERROR (vision):", e)
            return "⚠️ Could not analyze the image."
