import os
import asyncio
import requests
import json
from dotenv import load_dotenv
from browser_use import Agent, Browser, ChatGoogle

load_dotenv()

CDP_HTTP = "http://localhost:9222"
TASK_TIMEOUT_SECONDS = 3600  # hard ceiling so nothing hangs forever (1 hour)

def isolate_tab_monkeypatch(target_url: str, target_title: str = "", allow_new_tabs: bool = False):
    """
    Monkeypatches browser_use SessionManager to filter the initial targets list.
    It resolves the target dynamically at connection time.
    """
    if not target_url:
        return None
        
    try:
        from browser_use.browser.session_manager import SessionManager
        orig_init = SessionManager._initialize_existing_targets
        
        async def patched_init(self):
            cdp_client = self.browser_session._cdp_client_root
            if not cdp_client: 
                return await orig_init(self)
                
            orig_getTargets = cdp_client.send.Target.getTargets
            
            async def mock_getTargets(*args, **kwargs):
                result = await orig_getTargets(*args, **kwargs)
                
                # Resolve dynamically using the actual targets from CDP
                current_target_id = None
                
                # 1. Exact URL match
                for t in result.get('targetInfos', []):
                    if t.get('type') == 'page' and t.get('url') == target_url:
                        current_target_id = t.get('targetId')
                        break
                        
                # 2. Base URL match
                if not current_target_id:
                    base_url = target_url.split('?')[0].split('#')[0]
                    for t in result.get('targetInfos', []):
                        if t.get('type') == 'page' and t.get('url', '').startswith(base_url):
                            current_target_id = t.get('targetId')
                            break
                            
                # 3. Title match
                if not current_target_id and target_title:
                    for t in result.get('targetInfos', []):
                        if t.get('type') == 'page' and t.get('title') == target_title:
                            current_target_id = t.get('targetId')
                            break
                            
                # 4. Fallback to ANY active page if target detached (e.g., cross-process navigation)
                if not current_target_id:
                    for t in result.get('targetInfos', []):
                        if t.get('type') == 'page' and not t.get('url', '').startswith('devtools://'):
                            current_target_id = t.get('targetId')
                            break
                
                if current_target_id:
                    filtered_targets = []
                    for t in result.get('targetInfos', []):
                        if t.get('type') in ('page', 'tab'):
                            if t.get('targetId') == current_target_id:
                                filtered_targets.append(t)
                        else:
                            filtered_targets.append(t)
                    result['targetInfos'] = filtered_targets
                    
                return result
                
            cdp_client.send.Target.getTargets = mock_getTargets
            try:
                await orig_init(self)
            finally:
                cdp_client.send.Target.getTargets = orig_getTargets
                    
        # Apply patch
        SessionManager._initialize_existing_targets = patched_init
        return "dynamic_target"
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
    task_lower = task_description.lower()
    user_explicitly_wants_new_tab = any(kw in task_lower for kw in [
        "new tab", "open tab", "separate tab", "different tab"
    ])
    
    target_id = isolate_tab_monkeypatch(tab_url, tab_title, user_explicitly_wants_new_tab)
    
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
        models_list.append(ChatGoogle(model="gemini-3.1-flash-lite", api_key=gemini_key_1, max_retries=1))
        
    # Tier 2: Secondary Gemini Key
    if gemini_key_2:
        models_list.append(ChatGoogle(model="gemini-3.1-flash-lite", api_key=gemini_key_2, max_retries=1))
        
    # Tier 3: Fast NVIDIA NIM DeepSeek if key is present
    if nim_key:
        models_list.append(
            ChatOpenAI(
                model="deepseek-ai/deepseek-v4-flash",
                api_key=nim_key,
                base_url="https://integrate.api.nvidia.com/v1",
                max_retries=1
            )
        )
        
    if not models_list:
        raise ValueError("No valid API keys found for LLM setup. Please check .env file.")
        
    model = TieredFallbackLLM(models_list)

    # keep_alive=True is critical: without it, browser.kill() below could
    # tear down your dedicated Chrome instance instead of just releasing
    # this task's CDP session.
    try:
        browser = Browser(cdp_url=CDP_HTTP, keep_alive=True)
    except Exception as e:
        await send_update_callback("agent_update", f"Failed to connect to browser. Make sure Chrome is running with --remote-debugging-port=9222. Error: {e}")
        raise e

    # ── Pre-flight check has been removed because it is now handled dynamically
    # inside isolate_tab_monkeypatch at connection time.

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

    enhanced_task = (
        f"CURRENT PAGE: {tab_title} ({tab_url})\n"
        f"TASK: {task_description}\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. You MUST perform this task on the CURRENT PAGE. Do NOT navigate away to a different website unless explicitly told to do so in the TASK.\n"
        "2. ONLY DO EXACTLY WHAT IS ASKED. If the user asks to 'apply to this job', assume the job is already on the screen. Do NOT search for new jobs, do NOT open new tabs, and do NOT perform actions that were not explicitly requested.\n"
        "3. If you encounter a form, job application, or login, you can use the 'get_personal_info' tool to retrieve the user's profile data (resume, skills, address, etc.) on demand. DO NOT hallucinate personal data.\n"
        "4. If asked to act on a single item (e.g., 'apply to this job'), do it EXACTLY ONCE. After the action succeeds, immediately use the 'done' action to finish.\n"
        "5. Do NOT use 'open_tab' or 'search_google' unless the task cannot be done on the current page."
    )

    from browser_use import Controller
    from browser_use.tools.views import NavigateAction
    from browser_use.agent.views import ActionResult
    
    # Task lower already computed above
    
    # ---- XenonNoNewTabTools: subclass that strips new_tab=True ----
    class XenonNoNewTabTools(Controller):
        """
        Subclass of browser-use Controller that prevents unwanted new tab opening.
        
        Layers of protection:
        1. Intercept the 'navigate' action in act() and force new_tab=False
           unless the user's task explicitly requested new tabs.
        2. Patch _detect_new_tab_opened out of click handlers so agent
           never auto-switches to tabs opened by target=_blank links.
        3. Inject a CDP script on every navigation that strips target=_blank.
        """
        
        def __init__(self, *args, allow_new_tabs: bool = False, **kwargs):
            super().__init__(*args, **kwargs)
            self._allow_new_tabs = allow_new_tabs
        
        async def act(self, action, browser_session, **kwargs):
            action_data = action.model_dump(exclude_unset=True)
            action_name = next(iter(action_data.keys())) if action_data else 'unknown'
            
            if action_name == 'navigate' and not self._allow_new_tabs:
                nav_params = action_data.get('navigate', {})
                if nav_params.get('new_tab'):
                    import logging
                    logging.getLogger('Xenon').warning(
                        f'[XenonNoNewTab] BLOCKED new_tab=True for navigate to '
                        f'{nav_params.get("url", "?")} — forced to current tab'
                    )
                    # Mutate the underlying Pydantic model so super().act() sees the change
                    nav_obj = getattr(action, action_name, None)
                    if nav_obj and hasattr(nav_obj, 'new_tab'):
                        nav_obj.new_tab = False
            
            result = await super().act(action, browser_session, **kwargs)
            
            if (action_name == 'click' and not self._allow_new_tabs
                    and isinstance(result, ActionResult) and result.extracted_content):
                if '. Automatically switched to new tab' in result.extracted_content:
                    result.extracted_content = result.extracted_content.replace(
                        '. Automatically switched to new tab',
                        '. Stayed on current page.'
                    )
            
            return result
    
    # ---- Patch _detect_new_tab_opened globally ----
    import browser_use.tools.service as _tools_service
    
    _orig_detect = getattr(_tools_service, '_detect_new_tab_opened', None)
    if _orig_detect:
        async def _patched_detect_new_tab(browser_session, tabs_before):
            if user_explicitly_wants_new_tab:
                return await _orig_detect(browser_session, tabs_before)
            return ''
        _tools_service._detect_new_tab_opened = _patched_detect_new_tab
    
    # ---- Build exclude actions (correct action names for v0.13.6) ----
    exclude_actions = []
    
    if not user_explicitly_wants_new_tab:
        exclude_actions.append('open_tab')
        exclude_actions.append('switch')
        exclude_actions.append('close')
    if "search google" not in task_lower and "google search" not in task_lower:
        exclude_actions.append('search')
    
    controller = XenonNoNewTabTools(
        exclude_actions=exclude_actions if exclude_actions else None,
        allow_new_tabs=user_explicitly_wants_new_tab
    )
    
    @controller.action("Get user personal profile data, resume details, and skills to fill out forms and applications.")
    async def get_personal_info():
        try:
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            info_path = os.path.join(root_dir, "personal_info.json")
            if os.path.exists(info_path):
                with open(info_path, "r", encoding="utf-8") as f:
                    return f"USER PROFILE DATA:\n{f.read()}"
        except Exception as e:
            return f"Error retrieving personal info: {e}"
        return "No personal profile data found."
    
    # ---- Override system prompt ----
    override_system_message = """<SYSTEM_OVERRIDE>
CRITICAL: This agent runs in STAY-ON-CURRENT-PAGE mode.
- NEVER open new tabs. NEVER use navigate with new_tab=true.
- ALWAYS work within the current page/tab. All navigation, clicking, typing, extraction MUST happen on the current tab.
- If you clicked a link and a new tab opened, IGNORE it — stay on the current tab and continue your task there.
- The only exception: if the USER REQUEST explicitly says "open a new tab" or "search Google", you may navigate or search.
- Your goal is speed. Combine actions aggressively. Use input+click, click+click, input+input in a single step whenever they don't change the page state between actions.
- AVOID REPETITIVE LOOPS. If asked to process many items (e.g. delete all emails), find and use bulk actions like "Select All" checkboxes. DO NOT click items one-by-one!
- If you need to navigate to a URL, ALWAYS navigate in the CURRENT tab (new_tab=false).
- After navigating, the page changes — wait for the new page state before acting further.

ELEMENT INTERACTION RULES (CRITICAL - READ CAREFULLY):
- The browser gives you a list of numbered interactive elements (e.g. [1], [2], [3]...) in every step. These are the ONLY elements you can directly click or type into.
- `find_elements` is a SEARCH TOOL ONLY — it tells you if something exists, but it does NOT give you an interaction index.
- After calling `find_elements` ONCE and confirming an element exists, DO NOT call `find_elements` again on the same page. Instead:
  * Look at the numbered elements list in the current page state.
  * Find the matching element by its label/placeholder/text.
  * Use `click_element` or `input_text` with that number to interact.
- If the element is visible in the page but not numbered (not interactable), use `evaluate` to click/type via JavaScript.
- NEVER call `find_elements` more than once looking for the same element. It is a loop and wastes tokens.
</SYSTEM_OVERRIDE>"""
    
    agent = Agent(
        task=enhanced_task,
        llm=model,
        browser=browser,
        controller=controller,
        register_new_step_callback=step_callback,
        use_thinking=False,
        use_judge=False,
        enable_planning=False,
        directly_open_url=False,
        max_actions_per_step=3,
        max_failures=3,
        loop_detection_enabled=True,
        extend_system_message=override_system_message,
    )

    if not user_explicitly_wants_new_tab and target_id:
        try:
            import websockets
            targets = requests.get(f"{CDP_HTTP}/json").json()
            matching_targets = [t for t in targets if t.get('id') == target_id]
            if matching_targets and 'webSocketDebuggerUrl' in matching_targets[0]:
                ws_url = matching_targets[0]['webSocketDebuggerUrl']
                target_blank_js = (
                    "(function(){"
                    "document.addEventListener('click', function(e) {"
                    "  var a = e.target.closest && e.target.closest('a');"
                    "  if (a && (a.target === '_blank' || a.target === '_new' || a.target === 'blank')) {"
                    "    a.target = '_self';"
                    "  }"
                    "}, true);"
                    "window.open = function(url) { window.location.href = url; return window; };"
                    "})();"
                )
                async with websockets.connect(ws_url) as ws:
                    await ws.send(json.dumps({
                        "id": 1,
                        "method": "Page.addScriptToEvaluateOnNewDocument",
                        "params": {"source": target_blank_js}
                    }))
                    await ws.send(json.dumps({
                        "id": 2,
                        "method": "Runtime.evaluate",
                        "params": {"expression": target_blank_js}
                    }))
                print("[Xenon] Successfully injected target=_blank stripper directly onto target tab via CDP")
        except Exception as ex:
            print(f"[Xenon] Warning: CDP script injection failed: {ex}")

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