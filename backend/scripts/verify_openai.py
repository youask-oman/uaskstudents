import os
import asyncio
from openai import AsyncOpenAI

async def verify():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: No API key found in environment")
        return

    print(f"Checking key: {api_key[:15]}... (Length: {len(api_key)})")
    
    client = AsyncOpenAI(api_key=api_key)
    
    try:
        response = await client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5
        )
        print("SUCCESS: API key works.")
        print("Response:", response.choices[0].message.content)
    except Exception as e:
        print("FAILURE: API key rejected.")
        print("Error:", str(e))

if __name__ == "__main__":
    asyncio.run(verify())
