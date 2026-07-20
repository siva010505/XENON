import os
import asyncio
from dotenv import load_dotenv
from browser_use import Agent, Browser, ChatGoogle

load_dotenv()

# Apply monkeypatches to avoid watchdogs timing out on suspended background tabs
try:
    from browser_use.browser.watchdogs.popups_watchdog import PopupsWatchdog
    from browser_use.browser.watchdogs.downloads_watchdog import DownloadsWatchdog
    
    async def on_TabCreatedEvent(*args, **kwargs):
        pass
        
    PopupsWatchdog.on_TabCreatedEvent = on_TabCreatedEvent
    DownloadsWatchdog.on_TabCreatedEvent = on_TabCreatedEvent
except ImportError as e:
    print("Failed to monkeypatch:", e)

async def main():
    model = ChatGoogle(
        model="gemini-2.5-flash",
        api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    )
    browser = Browser(cdp_url="http://localhost:9222", keep_alive=True)
    agent = Agent(task="search aws", llm=model, browser=browser, use_thinking=False)
    
    try:
        history = await asyncio.wait_for(agent.run(max_steps=2), timeout=120)
        print("Run finished!")
        if history and hasattr(history, 'history') and history.history:
            print("Step count:", len(history.history))
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        await browser.kill()

if __name__ == "__main__":
    asyncio.run(main())
