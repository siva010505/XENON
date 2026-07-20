import asyncio
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser

load_dotenv()

class CustomChat(ChatOpenAI):
    @property
    def provider(self):
        return "custom"
        
    @property
    def model(self):
        return getattr(self, "model_name", "unknown")

async def main():
    llm = CustomChat(
        model="mistralai/mistral-large-2-instruct",
        api_key=os.getenv("NVIDIA_API_KEY"),
        base_url="https://integrate.api.nvidia.com/v1"
    )
    
    try:
        browser = Browser(cdp_url="http://localhost:9222")
    except Exception as e:
        print("Browser init error:", e)
        return

    agent = Agent(
        task="search aws",
        llm=llm,
        browser=browser,
        use_thinking=False
    )
    
    try:
        print("Starting agent run...")
        history = await agent.run(max_steps=1)
        print("Finished agent run!")
        if history.history:
            print("Result:", history.history[-1].result)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
