import os
import asyncio
import requests
from dotenv import load_dotenv
from browser_use import Agent, Browser, ChatGoogle

load_dotenv()

CDP_HTTP = "http://localhost:9222"
TASK_TIMEOUT_SECONDS = 3600  # hard ceiling so nothing hangs forever (1 hour)

def isolate_tab_monkeypatch(target_url: str, target_title: str = ""):
    """
    Monkeypatches browser_use SessionManager to completely ignore all background tabs 
    except the one matching target_url. This prevents watchdogs and CDP from timing out
    when the browser has dozens of heavy/suspended tabs.
    """
    if not target_url:
        return None
        
    try:
        targets = requests.get(f"{CDP_HTTP}/json").json()
        target_id = None
        
        # 1. Try exact URL match
        for t in targets:
            if t.get('type') == 'page' and t.get('url') == target_url:
                target_id = t.get('id')
                break
                
        # 2. Try prefix/base URL match if exact fails
        if not target_id:
            base_url = target_url.split('?')[0].split('#')[0]
            for t in targets:
                if t.get('type') == 'page' and t.get('url', '').startswith(base_url):
                    target_id = t.get('id')
                    break
                    
        # 3. Try Title match if URL still fails
        if not target_id and target_title:
            for t in targets:
                if t.get('type') == 'page' and t.get('title') == target_title:
                    target_id = t.get('id')
                    break
        
        if not target_id:
            print(f"Could not find target matching url: {target_url} or title: {target_title}")
            return None
            
        print(f"Isolating browser-use to single tab: {target_id}")
        
        from browser_use.browser.session_manager import SessionManager
        
        orig_handle = SessionManager._handle_target_attached
        
        orig_init = SessionManager._initialize_existing_targets
        
        async def patched_init(self):
            cdp_client = self.browser_session._cdp_client_root
            if not cdp_client: 
                return await orig_init(self)
                
            orig_getTargets = cdp_client.send.Target.getTargets
            
            async def mock_getTargets(*args, **kwargs):
                result = await orig_getTargets(*args, **kwargs)
                filtered_infos = []
                for target_info in result.get('targetInfos', []):
                    tid = target_info.get('targetId')
                    ttype = target_info.get('type')
                    if ttype in ('page', 'tab') and tid != target_id:
                        continue # IGNORE other tabs
                    filtered_infos.append(target_info)
                return {'targetInfos': filtered_infos}
                
            cdp_client.send.Target.getTargets = mock_getTargets
            try:
                await orig_init(self)
            finally:
                cdp_client.send.Target.getTargets = orig_getTargets
                    
        async def patched_handle(self, event):
            info = event.get('targetInfo', {})
            tid = info.get('targetId')
            ttype = info.get('type')
            
            if ttype in ('page', 'tab') and tid != target_id:
                # We still allow new blank tabs in case the agent creates them
                if info.get('url') not in ('about:blank', ''):
                    return # IGNORE
                    
            await orig_handle(self, event)
            
        # Apply patches
        SessionManager._initialize_existing_targets = patched_init
        SessionManager._handle_target_attached = patched_handle
        
        return target_id
    except Exception as e:
        print(f"Monkeypatch setup failed: {e}")
        return None


async def run_browser_task(task_description: str, send_update_callback, tab_url: str = "", tab_title: str = ""):
    """
    Executes a browser automation task using browser-use's native Gemini
    integration (ChatGoogle). Connects to the existing dedicated Chrome
    instance on CDP_HTTP. Does NOT touch existing tabs — each tab is
    expected to run its own Xenon session independently.
    """
    
    # Apply monkeypatch before creating the Browser instance
    target_id = isolate_tab_monkeypatch(tab_url, tab_title)
    
    from browser_use.llm.openai.chat import ChatOpenAI
    from browser_use.llm.google.chat import ChatGoogle
    from browser_use.agent.views import AgentOutput
    import re
    
    # DeepSeek V4 on NIM sometimes returns markdown text or conversational prefixes
    # before the JSON object. We monkeypatch the Pydantic parser for AgentOutput
    # to extract the JSON. By using super(AgentOutput, cls), we ensure Pydantic's
    # dynamic subclassing for ActionModel works flawlessly!
    @classmethod
    def clean_validate_json(cls, json_data: str, *args, **kwargs):
        import json
        json_data = re.sub(r'^```json\s*', '', json_data)
        json_data = re.sub(r'\s*```$', '', json_data)
        match = re.search(r'\{.*\}', json_data, re.DOTALL)
        if match:
            json_data = match.group(0)
            
        return super(AgentOutput, cls).model_validate_json(json_data, *args, **kwargs)
        
    AgentOutput.model_validate_json = clean_validate_json
    
    class TieredFallbackLLM:
        def __init__(self, models: list):
            self.models = [m for m in models if m is not None]
            if not self.models:
                raise ValueError("No valid models provided to TieredFallbackLLM")
            self.current_idx = 0
    
        @property
        def current_model(self):
            return self.models[self.current_idx]
    
        @property
        def model(self):
            return getattr(self.current_model, 'model', 'tiered_fallback')
            
        @property
        def model_name(self):
            return getattr(self.current_model, 'model_name', self.model)
            
        @property
        def provider(self):
            return getattr(self.current_model, 'provider', 'unknown')
            
        @property
        def name(self):
            return getattr(self.current_model, 'name', 'tiered_fallback_llm')
    
        async def ainvoke(self, messages, output_format=None, **kwargs):
            last_error = None
            for i in range(self.current_idx, len(self.models)):
                self.current_idx = i
                try:
                    print(f"[TieredFallbackLLM] Attempting request with {self.model} via {self.provider}...")
                    response = await self.models[i].ainvoke(messages, output_format=output_format, **kwargs)
                    return response
                except Exception as e:
                    print(f"[TieredFallbackLLM] ERROR with {self.model}: {e}. Falling back to next...")
                    last_error = e
            
            print("[TieredFallbackLLM] FATAL: All fallback models exhausted.")
            raise last_error

    gemini_key_1 = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    gemini_key_2 = os.getenv("GEMINI_API_KEY_2")
    nim_key = os.getenv("NVIDIA_API_KEY")
    
    models_list = []
    
    # Tier 1: Primary Gemini Key
    if gemini_key_1:
        models_list.extend([
            ChatGoogle(model="gemini-3.1-flash-lite", api_key=gemini_key_1),
            ChatGoogle(model="gemini-3-flash", api_key=gemini_key_1),
            ChatGoogle(model="gemini-3.5-flash", api_key=gemini_key_1)
        ])
        
    # Tier 2: Secondary Gemini Key
    if gemini_key_2:
        models_list.extend([
            ChatGoogle(model="gemini-3.1-flash-lite", api_key=gemini_key_2),
            ChatGoogle(model="gemini-3-flash", api_key=gemini_key_2),
            ChatGoogle(model="gemini-3.5-flash", api_key=gemini_key_2)
        ])
        
    # Tier 3: NIM DeepSeek
    if nim_key:
        models_list.append(
            ChatOpenAI(
                model="deepseek-ai/deepseek-v4-flash",
                api_key=nim_key,
                base_url="https://integrate.api.nvidia.com/v1"
            )
        )
        
    model = TieredFallbackLLM(models_list)

    # keep_alive=True is critical: without it, browser.kill() below could
    # tear down your dedicated Chrome instance instead of just releasing
    # this task's CDP session.
    try:
        browser = Browser(cdp_url=CDP_HTTP, keep_alive=True)
    except Exception as e:
        await send_update_callback("agent_update", f"Failed to connect to browser. Make sure Chrome is running with --remote-debugging-port=9222. Error: {e}")
        raise e

    def step_callback(state, output, step_number):
        if not output or not hasattr(output, 'action'):
            return
            
        for act in output.action:
            if not act: continue
            try:
                act_data = act.model_dump(exclude_none=True)
                for action_name, action_params in act_data.items():
                    print(f"[DEBUG] Action triggered: {action_name}")
                    msg = ""
                    if action_name == 'go_to_url':
                        msg = f"Navigating to {action_params.get('url', 'URL')}"
                    elif action_name == 'input':
                        msg = f"Typing '{action_params.get('text', '')}'"
                    elif action_name == 'send_keys':
                        msg = f"Pressing keys"
                    elif action_name == 'click':
                        msg = "Clicking an element"
                    elif action_name == 'scroll':
                        msg = "Scrolling page"
                    elif action_name == 'search_google':
                        msg = f"Searching Google"
                    elif action_name == 'extract':
                        msg = "Extracting page data"
                    elif action_name == 'switch':
                        msg = "Switching tabs"
                    elif action_name == 'open_tab':
                        msg = "Opening new tab"
                    elif action_name == 'done':
                        msg = "Wrapping up task"
                        
                    if msg:
                        asyncio.create_task(send_update_callback("agent_update", msg))
            except Exception as e:
                print(f"[DEBUG step_callback] Error: {e}")

    personal_info = ""
    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        info_path = os.path.join(root_dir, "personal_info.json")
        if os.path.exists(info_path):
            with open(info_path, 'r', encoding='utf-8') as f:
                personal_info = f"\n\nUSER PROFILE DATA (Use this to fill forms, job applications, or logins if required):\n{f.read()}"
    except Exception:
        pass

    enhanced_task = (
        f"CURRENT PAGE: {tab_title} ({tab_url})\n"
        f"TASK: {task_description}\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. You MUST perform this task on the CURRENT PAGE. Do NOT navigate away to a different website unless explicitly told to do so in the TASK.\n"
        "2. ONLY DO EXACTLY WHAT IS ASKED. If the user asks to 'apply to this job', assume the job is already on the screen. Do NOT search for new jobs, do NOT open new tabs, and do NOT perform actions that were not explicitly requested.\n"
        "3. The USER PROFILE DATA provided below is ONLY to be used for filling out forms or answering specific questions on the current page. Do NOT use it to initiate searches.\n"
        "4. If asked to act on a single item (e.g., 'apply to this job'), do it EXACTLY ONCE. After the action succeeds, immediately use the 'done' action to finish.\n"
        "5. Do NOT use 'open_tab' or 'search_google' unless the task cannot be done on the current page."
        f"{personal_info}"
    )

    from browser_use import Controller
    
    exclude_actions = []
    task_lower = task_description.lower()
    
    # Only disable these tools if the user didn't explicitly ask for them
    if "new tab" not in task_lower and "open tab" not in task_lower:
        exclude_actions.append("open_tab")
    if "search google" not in task_lower and "google search" not in task_lower:
        exclude_actions.append("search_google")
    if "navigate to" not in task_lower and "go to" not in task_lower and "new tab" not in task_lower and "open tab" not in task_lower:
        exclude_actions.append("go_to_url")
        
    controller = Controller(exclude_actions=exclude_actions if exclude_actions else None)

    agent = Agent(
        task=enhanced_task,
        llm=model,
        browser=browser,
        controller=controller,
        register_new_step_callback=step_callback,
        use_thinking=False,
        use_judge=False,
        max_failures=3,                 # Stop quickly if it fails 3 times in a row
        loop_detection_enabled=True,
    )

    try:
        # Hard timeout — turns a silent infinite hang into a clean,
        # reportable failure instead of leaving the panel on "Processing..."
        # We enforce max_steps=100 to allow long 80-step tasks, while still
        # relying on loop_detection and max_failures to prevent infinite hangs.
        history = await asyncio.wait_for(agent.run(max_steps=100), timeout=TASK_TIMEOUT_SECONDS)

        if history and hasattr(history, 'history') and history.history:
            # Check for max steps
            if len(history.history) >= 100:
                return "Failed: Agent reached the maximum limit of 100 steps without finishing."
                
            last_step = history.history[-1]
            
            # Check for internal agent errors (like loops or repeated failures)
            if hasattr(last_step, 'result') and last_step.result and len(last_step.result) > 0:
                errors = [r.error for r in last_step.result if hasattr(r, 'error') and r.error]
                if errors:
                    err_msg = " | ".join(errors)
                    return f"Failed: {err_msg}"
                    
                if last_step.result[-1].extracted_content:
                    return last_step.result[-1].extracted_content

            # Fallback to the 'done' text from the model output
            for step in reversed(history.history):
                if hasattr(step, 'model_output') and step.model_output and hasattr(step.model_output, 'action'):
                    for act in step.model_output.action:
                        try:
                            act_data = act.model_dump(exclude_none=True)
                            if 'done' in act_data and 'text' in act_data['done']:
                                return f"Summary: {act_data['done']['text']}"
                        except Exception:
                            continue

        return "Task completed successfully."

    except asyncio.TimeoutError:
        return "Failed: Task timed out. The 1-hour limit was reached or the browser completely hung."

    except Exception as e:
        # Instead of crashing the backend or sending a massive Python traceback to the UI,
        # we return a clean explanation of the crash.
        err_str = str(e)
        if "TargetClosed" in err_str or "Target page, context or browser has been closed" in err_str:
            return "Failed: The browser tab was closed or Chrome crashed."
        return f"Failed: Internal error ({err_str})"

    finally:
        # Always release this task's CDP session so sessions don't
        # accumulate across successive tasks. keep_alive=True above
        # ensures this only disconnects — it does not close Chrome
        # or any of your open tabs.
        try:
            await browser.kill()
        except Exception:
            pass