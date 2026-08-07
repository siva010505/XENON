import sys
import os
os.environ["ANONYMIZED_TELEMETRY"] = "false"
log_path = os.path.join(os.path.dirname(__file__), "server_debug.log")
try:
    if sys.stdout is None:
        sys.stdout = open(log_path, "a")
    if sys.stderr is None:
        sys.stderr = open(log_path, "a")
except Exception:
    pass

from dotenv import load_dotenv
load_dotenv()

import argparse
import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

class WebuiManager:
    def __init__(self):
        self.bu_chat_history = []
        self.bu_current_task = None
        self.bu_browser = None
        self.bu_browser_context = None
        self.bu_controller = None
        self.bu_agent = None
        self.bu_agent_task_id = None
        self.bu_response_event = None
        self.bu_user_help_response = None

    def init_browser_use_agent(self):
        pass

from src.agent.browser_use.browser_use_agent import BrowserUseAgent
from src.browser.custom_browser import CustomBrowser
from src.browser.custom_context import CustomBrowserContext
from src.controller.custom_controller import CustomController
from src.utils import llm_provider, config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

webui_manager: Optional[WebuiManager] = None
_online_queues: Dict[str, asyncio.Queue] = {}


class TaskRequest(BaseModel):
    task: str
    max_steps: int = 100
    max_actions: int = 1
    max_input_tokens: int = 128000
    llm_provider: Optional[str] = None
    llm_model_name: Optional[str] = None
    llm_temperature: float = 0.6
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    use_vision: bool = True
    ollama_num_ctx: int = 16000
    tool_calling_method: str = "auto"
    override_system_prompt: Optional[str] = None
    extend_system_prompt: Optional[str] = None
    planner_llm_provider: Optional[str] = None
    planner_llm_model_name: Optional[str] = None
    planner_llm_temperature: float = 0.6
    planner_llm_base_url: Optional[str] = None
    planner_llm_api_key: Optional[str] = None
    planner_use_vision: bool = False
    planner_ollama_num_ctx: int = 16000
    cdp_url: Optional[str] = None
    wss_url: Optional[str] = None
    target_url: Optional[str] = None
    browser_binary_path: Optional[str] = None
    browser_user_data_dir: Optional[str] = None
    headless: bool = False
    disable_security: bool = False
    keep_browser_open: bool = True
    window_width: int = 1280
    window_height: int = 1100
    save_recording_path: Optional[str] = None
    save_trace_path: Optional[str] = None
    save_agent_history_path: str = "./tmp/agent_history"
    save_download_path: str = "./tmp/downloads"
    mcp_server_config: Optional[Dict[str, Any]] = None
    personal_data: Optional[List[Dict[str, str]]] = None

    class Config:
        extra = "allow"


def parse_task_request(payload: Dict[str, Any]) -> TaskRequest:
    """Normalize camelCase and simplified keys to TaskRequest schema."""
    field_map = {
        "provider": "llm_provider",
        "llmProvider": "llm_provider",
        "model": "llm_model_name",
        "llmModelName": "llm_model_name",
        "apiKey": "llm_api_key",
        "llmApiKey": "llm_api_key",
        "temperature": "llm_temperature",
        "llmTemperature": "llm_temperature",
        "baseUrl": "llm_base_url",
        "llmBaseUrl": "llm_base_url",
        "cdpUrl": "cdp_url",
        "wssUrl": "wss_url",
        "targetUrl": "target_url",
        "maxSteps": "max_steps",
        "maxActions": "max_actions",
        "maxInputTokens": "max_input_tokens",
        "useVision": "use_vision",
        "keepOpen": "keep_browser_open",
        "keepBrowserOpen": "keep_browser_open",
        "personalData": "personal_data",
    }
    normalized = {}
    for k, v in payload.items():
        if k == "settings" and isinstance(v, dict):
            for sk, sv in v.items():
                target_key = field_map.get(sk, sk)
                normalized[target_key] = sv
        else:
            target_key = field_map.get(k, k)
            normalized[target_key] = v
    return TaskRequest(**normalized)


class HelpResponse(BaseModel):
    response: str


async def emit_event(event_type: str, data: Any = None):
    for q in list(_online_queues.values()):
        try:
            await q.put(json.dumps({"type": event_type, "data": data}))
        except Exception:
            pass


DEFAULT_MODELS = {
    "google": "gemini-3.1-flash-lite",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
    "deepseek": "deepseek-chat",
    "ollama": "qwen2.5:7b",
    "grok": "grok-2",
    "mistral": "mistral-small",
}


async def _initialize_llm(
    provider: Optional[str],
    model_name: Optional[str],
    temperature: float,
    base_url: Optional[str],
    api_key: Optional[str],
    num_ctx: Optional[int] = None,
):
    provider = provider or os.getenv("DEFAULT_LLM", "google")
    model_name = model_name or DEFAULT_MODELS.get(provider, "gemini-3.1-flash-lite")

    if api_key:
        if provider == "google":
            os.environ["GOOGLE_API_KEY"] = api_key
            os.environ["GEMINI_API_KEY"] = api_key
        elif provider == "openai":
            os.environ["OPENAI_API_KEY"] = api_key
        elif provider == "anthropic":
            os.environ["ANTHROPIC_API_KEY"] = api_key
        elif provider == "deepseek":
            os.environ["DEEPSEEK_API_KEY"] = api_key
        elif provider in ["nvidia", "nim"]:
            os.environ["NVIDIA_API_KEY"] = api_key

    try:
        return llm_provider.get_llm_model(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            base_url=base_url or None,
            api_key=api_key or None,
            num_ctx=num_ctx if provider == "ollama" else None,
        )
    except Exception as e:
        logger.error(f"Failed to initialize LLM ({provider}/{model_name}): {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"LLM Error ({provider}/{model_name}): {e}. Check API key in side panel settings or .env file."
        )


def _format_agent_output(model_output) -> str:
    content = ""
    if model_output:
        try:
            action_dump = [
                action.model_dump(exclude_none=True) for action in model_output.action
            ]
            state_dump = model_output.current_state.model_dump(exclude_none=True)
            model_output_dump = {
                "current_state": state_dump,
                "action": action_dump,
            }
            json_string = json.dumps(model_output_dump, indent=4, ensure_ascii=False)
            content = json_string
        except Exception:
            content = str(model_output)
    return content.strip()


async def _handle_new_step(state, output, step_num: int):
    if not hasattr(webui_manager, "bu_chat_history"):
        webui_manager.bu_chat_history = []

    step_num_display = step_num - 1

    screenshot_b64 = None
    screenshot_data = getattr(state, "screenshot", None)
    if screenshot_data and isinstance(screenshot_data, str) and len(screenshot_data) > 100:
        screenshot_b64 = screenshot_data

    formatted_output = _format_agent_output(output)

    content_parts = [f"--- Step {step_num_display} ---"]
    if screenshot_b64:
        content_parts.append("[[screenshot]]" + screenshot_b64)

    content_parts.append(formatted_output)
    final_content = "\n\n".join(content_parts)

    chat_message = {"role": "assistant", "content": final_content}
    webui_manager.bu_chat_history.append(chat_message)

    await emit_event("step", {
        "step": step_num_display,
        "output": formatted_output,
        "screenshot": screenshot_b64,
    })
    await asyncio.sleep(0.05)


def _handle_done(history):
    steps_count = len(history.history) if hasattr(history, "history") else 0
    errors_str = None
    if steps_count == 0:
        final_summary = "Please check that your LLM API Key is configured in the Side Panel Settings or `.env` file.\nMake sure Chrome is open and running with `--remote-debugging-port=9222`."
    else:
        final_result = history.final_result()
        if final_result:
            final_summary = str(final_result).strip()
            # Strip any leading 'Result:' or '**Result:**' prefix
            if final_summary.lower().startswith("**result:**"):
                final_summary = final_summary[11:].strip()
            elif final_summary.lower().startswith("result:"):
                final_summary = final_summary[7:].strip()
        else:
            final_summary = "Task completed successfully."

        errors = history.errors()
        if errors and any(errors):
            non_empty_errors = [e for e in errors if e is not None and str(e).strip() != '']
            if non_empty_errors:
                errors_str = "\n".join([str(e) for e in non_empty_errors])

    webui_manager.bu_chat_history.append(
        {"role": "assistant", "content": final_summary}
    )
    return {"summary": final_summary, "errors": errors_str}


async def _ask_assistant_callback(query: str, browser_context) -> Dict[str, Any]:
    webui_manager.bu_chat_history.append({
        "role": "assistant",
        "content": f"**Need Help:** {query}\nPlease provide information or perform the required action in the browser, then type your response."
    })

    await emit_event("ask_user", {"query": query})

    webui_manager.bu_response_event = asyncio.Event()
    webui_manager.bu_user_help_response = None

    try:
        await asyncio.wait_for(webui_manager.bu_response_event.wait(), timeout=3600.0)
    except asyncio.TimeoutError:
        webui_manager.bu_response_event = None
        await emit_event("log", "Timeout: No response received.")
        return {"response": "Timeout: User did not respond."}

    response = webui_manager.bu_user_help_response
    webui_manager.bu_chat_history.append({"role": "user", "content": response})
    webui_manager.bu_response_event = None
    await emit_event("chat_update", webui_manager.bu_chat_history)
    return {"response": response}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global webui_manager
    webui_manager = WebuiManager()
    webui_manager.init_browser_use_agent()
    yield
    if webui_manager.bu_current_task and not webui_manager.bu_current_task.done():
        webui_manager.bu_current_task.cancel()
    if webui_manager.bu_browser_context:
        await webui_manager.bu_browser_context.close()
    if webui_manager.bu_browser:
        await webui_manager.bu_browser.close()


app = FastAPI(title="Browser Use API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/settings")
async def get_settings():
    return {
        "providers": {k: v for k, v in config.model_names.items()},
        "provider_display": config.PROVIDER_DISPLAY_NAMES,
        "default_provider": os.getenv("DEFAULT_LLM", "google"),
        "cdp_url": os.getenv("BROWSER_CDP", None),
        "browser_debugging_port": os.getenv("BROWSER_DEBUGGING_PORT", "9222"),
        "browser_debugging_host": os.getenv("BROWSER_DEBUGGING_HOST", "localhost"),
        "keep_browser_open": os.getenv("KEEP_BROWSER_OPEN", "true"),
    }


@app.post("/api/run-task")
async def run_task(payload: Dict[str, Any]):
    req = parse_task_request(payload)

    if not req.task.strip():
        raise HTTPException(status_code=400, detail="Task cannot be empty")

    if webui_manager.bu_current_task and not webui_manager.bu_current_task.done():
        raise HTTPException(status_code=400, detail="An agent task is already running")

    task_id = str(uuid.uuid4())
    _online_queues[task_id] = asyncio.Queue()

    async def run():
        try:
            await emit_event("status", "initializing")
            webui_manager.bu_chat_history.append({"role": "user", "content": req.task})
            await emit_event("chat_history", webui_manager.bu_chat_history)

            # Initialize LLM
            main_llm = await _initialize_llm(
                req.llm_provider or os.getenv("DEFAULT_LLM", "google"),
                req.llm_model_name,
                req.llm_temperature,
                req.llm_base_url,
                req.llm_api_key,
                req.ollama_num_ctx if (req.llm_provider or os.getenv("DEFAULT_LLM", "google")) == "ollama" else None,
            )

            planner_llm = None
            if req.planner_llm_provider:
                planner_llm = await _initialize_llm(
                    req.planner_llm_provider,
                    req.planner_llm_model_name,
                    req.planner_llm_temperature,
                    req.planner_llm_base_url,
                    req.planner_llm_api_key,
                    req.planner_ollama_num_ctx if req.planner_llm_provider == "ollama" else None,
                )

            # Controller
            async def ask_callback_wrapper(query, browser_context):
                return await _ask_assistant_callback(query, browser_context)

            if not webui_manager.bu_controller:
                webui_manager.bu_controller = CustomController(
                    ask_assistant_callback=ask_callback_wrapper
                )
                mcp_config = req.mcp_server_config
                await webui_manager.bu_controller.setup_mcp_client(mcp_config)

            # Browser setup
            should_close_browser = not req.keep_browser_open

            if should_close_browser:
                if webui_manager.bu_browser_context:
                    await webui_manager.bu_browser_context.close()
                    webui_manager.bu_browser_context = None
                if webui_manager.bu_browser:
                    await webui_manager.bu_browser.close()
                    webui_manager.bu_browser = None

            cdp_url = req.cdp_url or os.getenv("BROWSER_CDP", None) or f"http://127.0.0.1:{os.getenv('BROWSER_DEBUGGING_PORT', '9222')}"
            wss_url = req.wss_url or None

            # Always clean stale browser instance for CDP connections
            if cdp_url:
                if webui_manager.bu_browser:
                    try:
                        await webui_manager.bu_browser.close()
                    except Exception:
                        pass
                    webui_manager.bu_browser = None
                webui_manager.bu_browser_context = None

            if not webui_manager.bu_browser:
                from browser_use.browser.browser import BrowserConfig
                from browser_use.browser.context import BrowserContextConfig

                context_cfg = BrowserContextConfig(
                    no_viewport=True,
                )

                webui_manager.bu_browser = CustomBrowser(
                    config=BrowserConfig(
                        headless=req.headless,
                        disable_security=req.disable_security,
                        browser_binary_path=req.browser_binary_path or None,
                        extra_browser_args=[],
                        wss_url=wss_url,
                        cdp_url=cdp_url,
                        new_context_config=context_cfg,
                    )
                )

            # Connect or attach to current tab over CDP
            if cdp_url and webui_manager.bu_browser:
                try:
                    logger.info(f"Connecting CustomBrowser over CDP to {cdp_url} (target: {req.target_url})...")
                    webui_manager.bu_browser_context = await webui_manager.bu_browser.connect_over_cdp(cdp_url, req.target_url)
                    if webui_manager.bu_browser_context:
                        target_p = await webui_manager.bu_browser_context.get_current_page()
                        if target_p:
                            try:
                                await target_p.bring_to_front()
                            except Exception:
                                pass
                except Exception as cdp_err:
                    logger.warning(f"CDP connection failed: {cdp_err}")

            if not webui_manager.bu_browser_context:
                from browser_use.browser.context import BrowserContextConfig
                context_config = BrowserContextConfig(
                    trace_path=req.save_trace_path or None,
                    save_recording_path=req.save_recording_path or None,
                    save_downloads_path=req.save_download_path or None,
                    no_viewport=True,
                )
                webui_manager.bu_browser_context = (
                    await webui_manager.bu_browser.new_context(config=context_config)
                )

            webui_manager.bu_agent_task_id = task_id
            os.makedirs(
                os.path.join(req.save_agent_history_path or "./tmp/agent_history", task_id),
                exist_ok=True,
            )
            history_file = os.path.join(
                req.save_agent_history_path or "./tmp/agent_history",
                task_id,
                f"{task_id}.json",
            )
            gif_path = os.path.join(
                req.save_agent_history_path or "./tmp/agent_history",
                task_id,
                f"{task_id}.gif",
            )

            async def step_callback_wrapper(state, output, step_num):
                await _handle_new_step(state, output, step_num)

            def done_callback_wrapper(history):
                res = _handle_done(history)
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(emit_event("done", res if isinstance(res, dict) else {"summary": res}))
                except Exception as e:
                    logger.debug(f"Could not emit done event: {e}")

            tool_calling = req.tool_calling_method
            if tool_calling == "None":
                tool_calling = None

            default_extension = (
                "IMPORTANT RULES FOR EFFICIENT NAVIGATION:\n"
                "1. If clicking an element fails twice or toggles between tab headers without opening the target item (post, product, article, or listing), DO NOT keep clicking the tab headers. Scroll down 300-500 pixels to bring the actual content grid clearly into view.\n"
                "2. If clicking an element returns 'Element not clickable' or fails twice on the same index, DO NOT retry the exact same index. Try an alternative action such as scrolling, typing in search, or navigating to the target URL."
            )
            extend_system_msg = (
                f"{req.extend_system_prompt}\n{default_extension}"
                if req.extend_system_prompt
                else default_extension
            )

            # Prepend personal autofill info to task if user has stored details
            task_with_context = req.task
            if req.personal_data and len(req.personal_data) > 0:
                info_lines = "\n".join(
                    f"- {entry.get('key', '')}: {entry.get('value', '')}"
                    for entry in req.personal_data
                    if entry.get('key') and entry.get('value')
                )
                if info_lines:
                    task_with_context = (
                        f"[USER PERSONAL INFO - Use these details whenever filling forms, logging in, or entering personal information]:\n"
                        f"{info_lines}\n\n"
                        f"Task: {req.task}"
                    )

            # Always instantiate a fresh BrowserUseAgent for each task
            webui_manager.bu_agent = BrowserUseAgent(
                task=task_with_context,
                llm=main_llm,
                browser=webui_manager.bu_browser,
                browser_context=webui_manager.bu_browser_context,
                controller=webui_manager.bu_controller,
                register_new_step_callback=step_callback_wrapper,
                register_done_callback=done_callback_wrapper,
                use_vision=req.use_vision,
                override_system_message=req.override_system_prompt,
                extend_system_message=extend_system_msg,
                max_input_tokens=req.max_input_tokens,
                max_actions_per_step=req.max_actions,
                tool_calling_method=tool_calling,
                planner_llm=planner_llm,
                use_vision_for_planner=req.planner_use_vision if planner_llm else False,
                source="webui",
            )
            webui_manager.bu_agent.state.agent_id = task_id
            webui_manager.bu_agent.settings.generate_gif = gif_path

            await emit_event("status", "running")

            agent_coro = webui_manager.bu_agent.run(max_steps=req.max_steps)
            agent_task = asyncio.create_task(agent_coro)
            webui_manager.bu_current_task = agent_task

            last_chat_len = len(webui_manager.bu_chat_history)

            while not agent_task.done():
                is_paused = getattr(webui_manager.bu_agent, 'state', None)
                if is_paused:
                    is_paused = webui_manager.bu_agent.state.paused
                    is_stopped = webui_manager.bu_agent.state.stopped
                else:
                    is_paused = False
                    is_stopped = False

                if is_paused:
                    await emit_event("status", "paused")
                    while is_paused and not agent_task.done():
                        is_paused = webui_manager.bu_agent.state.paused if hasattr(webui_manager.bu_agent, 'state') else False
                        is_stopped = webui_manager.bu_agent.state.stopped if hasattr(webui_manager.bu_agent, 'state') else False
                        if is_stopped:
                            break
                        await asyncio.sleep(0.2)

                    if agent_task.done() or is_stopped:
                        break
                    await emit_event("status", "running")

                if is_stopped:
                    if not agent_task.done():
                        try:
                            await asyncio.wait_for(agent_task, timeout=1.0)
                        except (asyncio.TimeoutError, Exception):
                            agent_task.cancel()
                    break

                if (
                    hasattr(webui_manager, "bu_response_event")
                    and webui_manager.bu_response_event is not None
                ):
                    await emit_event("status", "waiting_help")
                    await emit_event("chat_history", webui_manager.bu_chat_history)
                    await webui_manager.bu_response_event.wait()
                    if not agent_task.done():
                        await emit_event("status", "running")

                if len(webui_manager.bu_chat_history) > last_chat_len:
                    await emit_event("chat_history", webui_manager.bu_chat_history)
                    last_chat_len = len(webui_manager.bu_chat_history)

                await asyncio.sleep(0.1)

            webui_manager.bu_agent.state.paused = False
            webui_manager.bu_agent.state.stopped = False

            try:
                if not agent_task.done():
                    await agent_task
                elif agent_task.exception():
                    agent_task.result()

                webui_manager.bu_agent.save_history(history_file)
                if os.path.exists(history_file):
                    await emit_event("history_file", history_file)

                if gif_path and os.path.exists(gif_path):
                    await emit_event("gif", gif_path)

            except asyncio.CancelledError:
                webui_manager.bu_chat_history.append(
                    {"role": "assistant", "content": "**Task Cancelled**."}
                )
                await emit_event("chat_history", webui_manager.bu_chat_history)
            except Exception as e:
                logger.error(f"Agent execution error: {e}", exc_info=True)
                error_msg = f"**Agent Execution Error:**\n```\n{type(e).__name__}: {e}\n```"
                webui_manager.bu_chat_history.append({"role": "assistant", "content": error_msg})
                await emit_event("error", str(e))
                await emit_event("chat_history", webui_manager.bu_chat_history)

            finally:
                webui_manager.bu_current_task = None

                if webui_manager.bu_browser_context:
                    try:
                        await webui_manager.bu_browser_context.remove_edge_light_from_all_pages()
                    except Exception:
                        pass

                if should_close_browser:
                    if webui_manager.bu_browser_context:
                        await webui_manager.bu_browser_context.close()
                        webui_manager.bu_browser_context = None
                    if webui_manager.bu_browser:
                        await webui_manager.bu_browser.close()
                        webui_manager.bu_browser = None

                await emit_event("status", "done")

        except Exception as e:
            logger.error(f"Setup error: {e}", exc_info=True)
            await emit_event("error", str(e))
            await emit_event("status", "error")
        finally:
            if task_id in _online_queues:
                del _online_queues[task_id]

    asyncio.create_task(run())
    return {"task_id": task_id, "status": "started"}


@app.post("/api/stop")
async def stop_agent():
    agent = webui_manager.bu_agent
    task = webui_manager.bu_current_task
    if agent and task and not task.done():
        agent.state.stopped = True
        agent.state.paused = False
        return {"status": "stopping"}
    return {"status": "not_running"}


@app.post("/api/pause")
async def pause_agent():
    agent = webui_manager.bu_agent
    task = webui_manager.bu_current_task
    if agent and task and not task.done():
        agent.pause()
        return {"status": "paused"}
    return {"status": "not_running"}


@app.post("/api/resume")
async def resume_agent():
    agent = webui_manager.bu_agent
    task = webui_manager.bu_current_task
    if agent and task and not task.done():
        agent.resume()
        return {"status": "resumed"}
    return {"status": "not_running"}


@app.post("/api/help-response")
async def help_response(req: HelpResponse):
    if webui_manager.bu_response_event:
        webui_manager.bu_user_help_response = req.response or "User provided no text."
        webui_manager.bu_response_event.set()
        return {"status": "submitted"}
    return {"status": "not_waiting"}


@app.get("/api/stream")
async def stream_events():
    queue_id = str(uuid.uuid4())
    queue = asyncio.Queue()
    _online_queues[queue_id] = queue

    async def event_generator():
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping', 'data': None})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _online_queues.pop(queue_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/api/chat-history")
async def get_chat_history():
    return {"history": getattr(webui_manager, "bu_chat_history", [])}


def main():
    parser = argparse.ArgumentParser(description="Browser Use API Server")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="IP address to bind to")
    parser.add_argument("--port", type=int, default=7788, help="Port to listen on")
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(app, host=args.ip, port=args.port)


if __name__ == "__main__":
    main()