import openai

class AIHelper:
    def __init__(self, openai_api_key: str):
        # API key set karo
        openai.api_key = openai_api_key
        # OpenRouter ka endpoint use karo
        openai.base_url = "https://openrouter.ai/api/v1"

    def chat_reply(self, prompt: str, memory=None):
        """
        prompt: user ka input
        memory: agar tum conversation history pass karna chaho
        """

        messages = []
        if memory:
            for role, content in memory:
                messages.append({"role": role, "content": content})

        # user ka latest input
        messages.append({"role": "user", "content": prompt})

        # OpenRouter API call
        response = openai.chat.completions.create(
            model="anthropic/claude-3.5-sonnet",   # 👈 default model
            messages=messages,
        )

        return response.choices[0].message["content"]
