
import os
from getpass import getpass
from groq import Groq

api_key = os.getenv("GROQ_API_KEY") or getpass("Enter GROQ_API_KEY: ")
client = Groq(api_key=api_key)

response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {
            "role": "user",
            "content": "أهلاً، عرّف نفسك بالعربي"
        }
    ]
)

print(response.choices[0].message.content)
