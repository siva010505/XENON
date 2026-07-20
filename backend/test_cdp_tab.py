import asyncio
import os
import requests
from browser_use import Agent, Browser, ChatGoogle
from dotenv import load_dotenv

load_dotenv()

async def main():
    # 1. Fetch all targets
    try:
        targets = requests.get("http://localhost:9222/json").json()
    except Exception as e:
        print("Failed to get targets:", e)
        return

    # 2. Find a valid page target
    page_target = None
    for t in targets:
        if t['type'] == 'page' and 'webSocketDebuggerUrl' in t:
            # Pick the first normal page (e.g., about:blank or something)
            if not t['url'].startswith('devtools://'):
                page_target = t
                break
    
    if not page_target:
        print("No valid page target found")
        return
        
    ws_url = page_target['webSocketDebuggerUrl']
    print("Using tab WebSocket URL:", ws_url)
    
    # 3. Try to use this ws_url as cdp_url
    model = ChatGoogle(model="gemini-2.5-flash", api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    
    try:
        browser = Browser(cdp_url=ws_url, keep_alive=True)
        agent = Agent(task="search aws", llm=model, browser=browser, use_thinking=False)
        history = await asyncio.wait_for(agent.run(max_steps=1), timeout=30)
        print("Success! Agent ran on single tab.")
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        await browser.kill()

if __name__ == "__main__":
    asyncio.run(main())
