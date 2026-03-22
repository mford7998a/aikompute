import httpx
import asyncio
import json

async def test_stream():
    url = "https://aikompute.com/v1/messages"
    headers = {
        "x-api-key": "sk-admin-Mv8Kp3Rq7YnT2Ws5",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True
    }
    
    print(f"Connecting to {url}...")
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                print(f"Status: {response.status_code}")
                if response.status_code != 200:
                    print(await response.aread())
                    return
                
                async for chunk in response.aiter_bytes():
                    print(f"[{len(chunk)} bytes]", end=" ", flush=True)
                    print(chunk.decode(errors="replace"))
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    asyncio.run(test_stream())
