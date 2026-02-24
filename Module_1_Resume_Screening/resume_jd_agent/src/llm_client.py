import openai

openai.api_key = "Enter your OpenAI API key here"

def call_llm(prompt, temperature=0):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature
    )
    return response["choices"][0]["message"]["content"]
