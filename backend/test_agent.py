import asyncio
from agent import run_browser_task

async def fake_callback(*args):
    print("Update:", args)

async def main():
    try:
        await run_browser_task("search aws", fake_callback)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
