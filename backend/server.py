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

# ----- Shared state: broadcast to ALL connected panels -----
_connected_panels: list[WebSocket] = []
_last_result: dict | None = None          # replay to freshly connected panels
_current_task: asyncio.Task | None = None  # global running agent task

async def _broadcast(msg_type: str, message: str):
    """Send to every connected panel. Silently drop dead connections."""
    global _last_result
    payload = json.dumps({"type": msg_type, "message": message})
    dead = []
    for ws in list(_connected_panels):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _connected_panels:
            _connected_panels.remove(ws)
    # Cache result/done messages so late-joiners see them
    if msg_type in ("result", "done", "agent_update"):
        _last_result = {"type": msg_type, "message": message}


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    global _current_task, _last_result

    await websocket.accept()
    _connected_panels.append(websocket)

    # If a task just finished, replay the result to this new panel
    if _last_result:
        try:
            await websocket.send_text(json.dumps(_last_result))
        except Exception:
            pass

    async def send_update(msg_type: str, message: str):
        """Send to ALL panels — silently handles dead sockets."""
        await _broadcast(msg_type, message)

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            action = payload.get("action")

            if action == "stop":
                if _current_task and not _current_task.done():
                    _current_task.cancel()
                    await send_update("agent_update", "Agent paused by user.")
                    await send_update("done", "Task stopped")
                continue

            task = payload.get("task")
            tab_url = payload.get("tabUrl", "")
            tab_title = payload.get("tabTitle", "")

            if task:
                # Clear stale last_result so new panel connects fresh
                _last_result = None

                async def run_task(t, url, title):
                    global _current_task
                    try:
                        result = await run_browser_task(t, send_update, url, title)
                        await send_update("result", str(result))
                        await send_update("done", "Task finished")
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        await send_update("result", f"Error: {str(e)}")
                        await send_update("done", "Task failed")

                _current_task = asyncio.create_task(run_task(task, tab_url, tab_title))

    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        if websocket in _connected_panels:
            _connected_panels.remove(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
