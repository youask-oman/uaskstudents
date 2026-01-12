import os
import asyncio
from openai import AsyncOpenAI

async def test_gpt5_mini():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: No API key found")
        return
    
    client = AsyncOpenAI(api_key=api_key)
    
    print("=" * 60)
    print("Testing GPT-5 Mini Model")
    print("=" * 60)
    
    # Test 1: List all models and check for gpt-5
    print("\n1. Checking available models...")
    try:
        models = await client.models.list()
        gpt5_models = [m.id for m in models.data if 'gpt-5' in m.id.lower()]
        if gpt5_models:
            print(f"✓ Found GPT-5 models: {gpt5_models}")
        else:
            print("✗ No GPT-5 models found")
            print("Available models containing 'gpt':")
            gpt_models = [m.id for m in models.data if 'gpt' in m.id.lower()][:10]
            for m in gpt_models:
                print(f"  - {m}")
    except Exception as e:
        print(f"✗ Error listing models: {e}")
    
    # Test 2: Try to use gpt-5-mini
    print("\n2. Testing gpt-5-mini with simple request...")
    try:
        response = await client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "Say 'Hello'"}],
            temperature=0.2,
            max_tokens=10
        )
        print(f"✓ SUCCESS: {response.choices[0].message.content}")
        print(f"  Model used: {response.model}")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        print(f"  Error type: {type(e).__name__}")
        if hasattr(e, 'response'):
            print(f"  Response: {e.response}")
    
    # Test 3: Test with temperature=0.7 (used in chat)
    print("\n3. Testing with temperature=0.7...")
    try:
        response = await client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "Say 'Test'"}],
            temperature=0.7,
            max_tokens=10
        )
        print(f"✓ SUCCESS with temp=0.7")
    except Exception as e:
        print(f"✗ FAILED with temp=0.7: {e}")

if __name__ == "__main__":
    asyncio.run(test_gpt5_mini())
