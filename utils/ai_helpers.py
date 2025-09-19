from openai import OpenAI

class AIHelper:
    def __init__(self, openai_api_key):
        self.client = OpenAI(api_key=openai_api_key)

    def chat_reply(self, user_message, memory=None):
        context = ""
        if memory:
            for role, content in memory:
                context += f"{role}: {content}\n"

        prompt = f"{context}\nUser: {user_message}\nAssistant:"

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",   # fast + cost-efficient
            messages=[
                {"role": "system", "content": "You are a helpful Telegram AI bot."},
                {"role": "user", "content": prompt}
            ]
        )

        return response.choices[0].message.content.strip()

    def vision_describe(self, image_url):
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",   # supports text+image input
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image in detail."},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ]
        )

        return response.choices[0].message.content.strip()
