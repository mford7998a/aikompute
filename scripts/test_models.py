import json
import time
import urllib.request
import urllib.error

# Gateway URL - modify if running on a different server or port
GATEWAY_URL = "https://aikompute.com/v1/chat/completions"
# The default master API key from docker-compose.yml
API_KEY = "sk-inf-TEDa_7H-H158YfN5IQHH3FDficRg55NLRwHqf4xVHwQ"

MODELS_TO_TEST = [
    # Antigravity (Gemini & Claude 4.6)
    "gemini-2.5-pro",
    "claude-sonnet-4-6",
    
    # Amazon Kiro (Claude 4.5)
    "claude-sonnet-4-5",
    
    # Gemini CLI / AI Studio
    "gemini-2.0-flash",
    
    # Qwen Code
    "qwen3-coder-plus",
    
    # GitHub Copilot Proxy
    "copilot-gpt-4o",
    "copilot-claude-sonnet",
    
    # GitHub Models
    "github-gpt-4o",
    "github-deepseek-v3"
]

def test_model(model_name):
    print(f"\n--- Testing Model: {model_name} ---")
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "Reply with precisely the word 'Success'."}
        ],
        "temperature": 0.1,
        "max_tokens": 10,
        "stream": True
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(GATEWAY_URL, data=data, headers=headers, method='POST')
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            elapsed_time = time.time() - start_time
            if response.status == 200:
                print(f"✅ Connection successful ({elapsed_time:.2f}s)! Waiting for chunks...")
                while True:
                    chunk = response.readline()
                    if not chunk:
                        break
                    print(f"Chunk: {chunk.decode('utf-8').strip()}")
                print("Stream finished.")
            else:
                print(f"❌ Failed ({elapsed_time:.2f}s) - Status: {response.status}")
                print(f"   Response text: {response.read().decode('utf-8')}")
                
    except urllib.error.HTTPError as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Failed ({elapsed_time:.2f}s) - Status: {e.code}")
        try:
            print(f"   Error detail: {e.read().decode('utf-8')}")
        except:
            print(f"   Response text: {e.reason}")
    except urllib.error.URLError as e:
        print(f"❌ Connection Error: {e.reason}")
    except Exception as e:
        print(f"❌ Unexpected Error: {str(e)}")

if __name__ == "__main__":
    print(f"Starting test script hitting gateway at {GATEWAY_URL}")
    print("Testing a selection of models from different providers...")
    
    for model in MODELS_TO_TEST:
        test_model(model)
        # Small delay to prevent hitting rate limits too quickly
        time.sleep(1)
        
    print("\n--- Testing Complete ---")
