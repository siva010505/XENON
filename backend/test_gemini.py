import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

ChatGoogleGenerativeAI.provider = property(lambda self: "google")
ChatGoogleGenerativeAI.model_name = property(lambda self: getattr(self, "model", "unknown"))

_original_ainvoke = ChatGoogleGenerativeAI.ainvoke
async def _custom_ainvoke(self, *args, **kwargs):
    print("\n--- AINVOKE CALLED ---")
    res = await _original_ainvoke(self, *args, **kwargs)
    print("\n--- LLM RESPONSE ---")
    print("Content:", res.content)
    print("Tool Calls:", getattr(res, "tool_calls", []))
    print("Additional Kwargs:", getattr(res, "additional_kwargs", {}))
    print("--- END LLM RESPONSE ---\n")
    return res

ChatGoogleGenerativeAI.ainvoke = _custom_ainvoke

model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY", "dummy")
)

print(hasattr(model, "provider"))
if hasattr(model, "provider"):
    print("Provider:", model.provider)

from browser_use import Agent
import asyncio

async def main():
    try:
        agent = Agent(task="search aws", llm=model, use_thinking=False)
        print("Agent initialized successfully! Running...")
        history = await agent.run(max_steps=3)
        print("Run finished!")
        print(history.history[-1] if history.history else "No history")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
