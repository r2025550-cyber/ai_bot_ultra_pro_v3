import openai

class AIHelper:
    def __init__(self,openai_api_key=None):
        if openai_api_key: openai.api_key=openai_api_key

    def chat_reply(self,text,memory,mode="normal"):
        sys={"role":"system","content":f"You are a helpful assistant. Mode:{mode}"}
        messages=[sys]+memory+[{"role":"user","content":text}]
        res=openai.ChatCompletion.create(model="gpt-4",messages=messages,max_tokens=300)
        return res["choices"][0]["message"]["content"].strip()

    def vision_describe(self,image_url):
        res=openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=[
                {"role":"system","content":"You are an image description assistant."},
                {"role":"user","content":[
                    {"type":"text","text":"Describe this image briefly."},
                    {"type":"image_url","image_url":{"url":image_url}}
                ]}
            ],
            max_tokens=100
        )
        return res["choices"][0]["message"]["content"].strip()
