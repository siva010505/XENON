import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://localhost:8000/ws/chat"
    try:
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({"task": "open gmail"}))
            print("Sent task: open gmail")
            while True:
                message = await asyncio.wait_for(websocket.recv(), timeout=120)
                print(f"Received: {message}")
                if "Task completed" in message or "Failed" in message:
                    break
    except Exception as e:
        print("Error or timeout:", e)

if __name__ == "__main__":
    asyncio.run(test_ws())
