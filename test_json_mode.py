from openai import OpenAI
client = OpenAI(
    api_key='sk-no-key-required',
    base_url='https://ollama.ptitaitutor.com/v1',
    default_headers={'ngrok-skip-browser-warning': 'true'}
)
response = client.chat.completions.create(
    model='deepseek-r1:14b',
    messages=[{'role': 'user', 'content': 'Generate a JSON object with a key "hello" and value "world"'}],
    response_format={'type': 'json_object'}
)
print(repr(response.choices[0].message.content))
