import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from agent import run_browser_task

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    async def send_update(msg_type: str, message: str):
        await websocket.send_text(json.dumps({
            "type": msg_type,
            "message": message
        }))

    try:
        current_task = None
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            action = payload.get("action")
            
            if action == "stop":
                if current_task and not current_task.done():
                    current_task.cancel()
                    await send_update("agent_update", "Agent paused by user.")
                    await send_update("done", "Task stopped")
                continue
                
            task = payload.get("task")
            tab_url = payload.get("tabUrl", "")
            tab_title = payload.get("tabTitle", "")
            
            if task:
                async def run_task(t, url, title):
                    try:
                        result = await run_browser_task(t, send_update, url, title)
                        await send_update("result", str(result))
                        await send_update("done", "Task finished")
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        await send_update("result", f"Error: {str(e)}")
                        await send_update("done", "Task failed")
                        
                current_task = asyncio.create_task(run_task(task, tab_url, tab_title))
    except WebSocketDisconnect:
        print("Client disconnected")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
