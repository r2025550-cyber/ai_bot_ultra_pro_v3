
# utils/ai_helpers.py
from openai import OpenAI

class AIHelper:
    def __init__(self, openai_api_key):
        # OpenAI client initialize
        self.client = OpenAI(api_key=openai_api_key)

    def chat_reply(self, user_message, memory=None):
        """
        Generate AI reply based on user message + short memory context
        """
        context = ""
        if memory:
            for role, content in memory:
                context += f"{role}: {content}\n"

        # Prompt build
        prompt = f"{context}\nUser: {user_message}\nAssistant:"

        # OpenAI ChatCompletion call (new SDK style)
        res = self.client.chat.completions.create(
            model="gpt-4o-mini",   # fast + cost efficient
            messages=[
                {"role": "system", "content": "You are a helpful Telegram AI bot."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300
        )
        return res.choices[0].message.content.strip()

    def vision_describe(self, image_url):
        """
        Describe an image using OpenAI Vision model
        """
        res = self.client.chat.completions.create(
            model="gpt-4o-mini",   # supports image input
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image in detail."},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            max_tokens=200
        )
        return res.choices[0].message.content.strip()
