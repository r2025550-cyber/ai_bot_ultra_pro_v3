import openai

class AIHelper:
    def __init__(self, openai_api_key: str):
        openai.api_key = openai_api_key
        openai.base_url = "https://openrouter.ai/api/v1"

    def chat_reply(self, prompt: str, memory=None):
        messages = []
        if memory:
            for role, content in memory:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": prompt})

        # Try Claude first, fallback GPT if error
        try:
            response = openai.chat.completions.create(
                model="anthropic/claude-3.5-sonnet",
                messages=messages,
            )
            return response.choices[0].message["content"]
        except Exception as e:
            try:
                response = openai.chat.completions.create(
                    model="openai/gpt-4o-mini",
                    messages=messages,
                )
                return response.choices[0].message["content"]
            except Exception:
                return "⚠️ Sorry, abhi thoda busy hoon 💖"
