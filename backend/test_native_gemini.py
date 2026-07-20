import os
import asyncio
from dotenv import load_dotenv
from browser_use import Agent, ChatGoogle

load_dotenv()

async def main():
    model = ChatGoogle(
        model="gemini-2.5-flash",
        api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    )
    agent = Agent(task="search aws", llm=model, use_thinking=False)
    
    try:
        history = await agent.run(max_steps=2)
        print("Run finished!")
        if history and hasattr(history, 'history') and history.history:
            last_step = history.history[-1]
            if hasattr(last_step, 'result') and last_step.result and len(last_step.result) > 0:
                print("Result error:", last_step.result[0].error)
            print("Step count:", len(history.history))
            print("First step output:", history.history[0].model_output if history.history else "None")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
