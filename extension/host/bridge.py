#!/usr/bin/env python3
"""
Browser Use Native Messaging Host
Communicates with Chrome extension via stdin/stdout JSON.
Connects to Chrome CDP (port 9222) and runs browser-use on the active tab.
"""

import sys
import os

# Disable browser-use telemetry BEFORE importing it
os.environ['BROWSER_USE_TELEMETRY'] = 'false'
os.environ['ANONYMIZED_TELEMETRY'] = 'false'

import json
import asyncio
import logging
import struct
import traceback
from typing import Optional, Dict, Any
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging to file only (stdout/stderr reserved for messaging)
log_file = Path(os.environ.get('TEMP', '.')) / 'browser_use_native_host.log'

# Remove all existing handlers from root logger
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='a')
    ],
    force=True
)
# Also disable propagation for common noisy loggers
for name in ['browser_use', 'playwright', 'httpx', 'httpcore']:
    logging.getLogger(name).setLevel(logging.WARNING)
    logging.getLogger(name).propagate = False

logger = logging.getLogger(__name__)
logger.info("=== Native host started ===")


from playwright.async_api import async_playwright
from browser_use.browser.browser import BrowserConfig
from browser_use.browser.context import BrowserContextConfig
from src.browser.custom_browser import CustomBrowser
from src.browser.custom_context import CustomBrowserContext
from src.agent.browser_use.browser_use_agent import BrowserUseAgent
from src.controller.custom_controller import CustomController
from src.utils.llm_provider import get_llm_model


class NativeMessagingHost:
    def __init__(self):
        self.running = True
        self.browser: Optional[CustomBrowser] = None
        self.browser_context: Optional[CustomBrowserContext] = None
        self.agent: Optional[BrowserUseAgent] = None
        self.controller: Optional[CustomController] = None
        self.current_task_id: Optional[str] = None
        self.cdp_url = "http://localhost:9222"
        self._playwright = None
        
    def send_message(self, message: Dict[str, Any]) -> None:
        """Send a message to Chrome via stdout."""
        encoded = json.dumps(message).encode('utf-8')
        sys.stdout.buffer.write(struct.pack('@I', len(encoded)))
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
        logger.debug(f"Sent: {message.get('type', 'unknown')}")

    def read_message(self) -> Optional[Dict[str, Any]]:
        """Read a message from Chrome via stdin."""
        try:
            logger.debug("Waiting for message on stdin...")
            raw_length = sys.stdin.buffer.read(4)
            logger.debug(f"Read raw_length: {raw_length}")
            if len(raw_length) == 0:
                logger.debug("No data (EOF)")
                return None
            length = struct.unpack('@I', raw_length)[0]
            logger.debug(f"Message length: {length}")
            message = sys.stdin.buffer.read(length).decode('utf-8')
            logger.debug(f"Received message: {message}")
            return json.loads(message)
        except (struct.error, json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Failed to read message: {e}")
            return None

    async def connect_to_cdp(self, cdp_url: str, target_url: str = None) -> bool:
        """Connect to Chrome via CDP using CustomBrowser's connect_over_cdp method."""
        self.cdp_url = cdp_url
        try:
            logger.info(f"Connecting to Chrome CDP: {cdp_url}")
            
            # Create CustomBrowser instance
            self.browser = CustomBrowser(
                config=BrowserConfig(
                    headless=False,
                    cdp_url=cdp_url,
                )
            )
            
            # Use the new connect_over_cdp method
            self.browser_context = await self.browser.connect_over_cdp(cdp_url, target_url)
            
            logger.info(f"Successfully connected to tab: {self.browser_context._connected_page.url if self.browser_context._connected_page else 'unknown'}")
            return True
             
        except Exception as e:
            logger.error(f"Failed to connect to CDP: {e}")
            traceback.print_exc(file=sys.stderr)
            return False

    async def ensure_connected(self, settings: Dict[str, Any]) -> bool:
        """Ensure we have a browser connection and context."""
        if self.browser_context and self.browser_context._connected_page:
            # Check if page is still valid
            try:
                _ = self.browser_context._connected_page.url
                return True
            except:
                logger.warning("Existing page connection lost, reconnecting...")
        
        cdp_url = settings.get('cdpUrl', self.cdp_url)
        target_url = settings.get('targetUrl')
        return await self.connect_to_cdp(cdp_url, target_url)

    async def run_agent_task(self, task: str, settings: Dict[str, Any]) -> None:
        """Run the browser-use agent on the active tab."""
        self.current_task_id = str(hash(task))[:8]
        
        try:
            # Send status update
            self.send_message({
                "type": "STATUS_CHANGE",
                "status": "running",
                "taskId": self.current_task_id
            })
            
            # Initialize LLM
            provider = settings.get('provider', 'google')
            model_name = settings.get('model', 'gemini-2.0-flash-exp')
            temperature = settings.get('temperature', 0.6)
            api_key = settings.get('apiKey', '')
            max_steps = settings.get('maxSteps', 100)
            use_vision = settings.get('useVision', True)
            
            llm = get_llm_model(
                provider=provider,
                model_name=model_name,
                temperature=temperature,
                api_key=api_key
            )
            
            if not self.controller:
                self.controller = CustomController()
            
            # Create agent with our pre-connected browser/context
            self.agent = BrowserUseAgent(
                task=task,
                llm=llm,
                browser=self.browser,
                browser_context=self.browser_context,
                controller=self.controller,
                register_new_step_callback=self.on_step,
                register_done_callback=self.on_done,
                use_vision=use_vision,
                max_steps=max_steps,
                source="sidepanel"
            )
            
            # Run agent
            history = await self.agent.run(max_steps=max_steps)
            
            # Send final result
            final_result = history.final_result()
            self.send_message({
                "type": "TASK_COMPLETE",
                "taskId": self.current_task_id,
                "result": final_result,
                "duration": history.total_duration_seconds(),
                "tokens": history.total_input_tokens()
            })
            
        except Exception as e:
            logger.error(f"Agent task error: {e}")
            traceback.print_exc(file=sys.stderr)
            self.send_message({
                "type": "TASK_ERROR",
                "taskId": self.current_task_id,
                "error": str(e)
            })
        finally:
            self.send_message({
                "type": "STATUS_CHANGE",
                "status": "idle",
                "taskId": self.current_task_id
            })

    async def on_step(self, agent: BrowserUseAgent) -> None:
        """Callback for each agent step."""
        try:
            state = agent.state
            step_num = len(state.history.history)
            
            # Get last action
            last_action = ""
            if state.history.history:
                last_output = state.history.history[-1].model_output
                if last_output and last_output.action:
                    actions = [str(a) for a in last_output.action]
                    last_action = "; ".join(actions[:3])
            
            self.send_message({
                "type": "STEP_UPDATE",
                "taskId": self.current_task_id,
                "step": step_num,
                "action": last_action,
                "url": state.url if hasattr(state, 'url') else ""
            })
        except Exception as e:
            logger.debug(f"Step callback error: {e}")

    async def on_done(self, history) -> None:
        """Callback when agent completes."""
        pass  # Handled in run_agent_task

    async def pause_agent(self) -> None:
        """Pause the running agent."""
        if self.agent:
            self.agent.pause()
            self.send_message({"type": "STATUS_CHANGE", "status": "paused", "taskId": self.current_task_id})

    async def resume_agent(self) -> None:
        """Resume the paused agent."""
        if self.agent:
            self.agent.resume()
            self.send_message({"type": "STATUS_CHANGE", "status": "running", "taskId": self.current_task_id})

    async def stop_agent(self) -> None:
        """Stop the running agent."""
        if self.agent:
            self.agent.stop()
            self.send_message({"type": "STATUS_CHANGE", "status": "stopped", "taskId": self.current_task_id})

    async def handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming message from Chrome extension."""
        msg_type = message.get('type')
        
        if msg_type == 'START_TASK':
            task = message.get('task', '')
            settings = message.get('settings', {})
            
            # Ensure connection
            if not await self.ensure_connected(settings):
                self.send_message({
                    "type": "TASK_ERROR",
                    "taskId": self.current_task_id or "unknown",
                    "error": "Failed to connect to Chrome. Make sure Chrome is running with --remote-debugging-port=9222"
                })
                return
            
            # Run task
            await self.run_agent_task(task, settings)
            
        elif msg_type == 'PAUSE':
            await self.pause_agent()
        elif msg_type == 'RESUME':
            await self.resume_agent()
        elif msg_type == 'STOP':
            await self.stop_agent()
        elif msg_type == 'GET_TABS':
            # Return list of tabs for picker (future use)
            tabs = []
            if self.browser and self.browser._playwright_browser:
                for ctx in self.browser._playwright_browser.contexts:
                    for page in ctx.pages:
                        try:
                            title = await page.title()
                            tabs.append({"url": page.url, "title": title})
                        except:
                            tabs.append({"url": page.url, "title": "Unknown"})
            self.send_message({"type": "TABS_LIST", "tabs": tabs})
        elif msg_type == 'PING':
            self.send_message({"type": "PONG"})

    async def run(self) -> None:
        """Main message loop."""
        logger.info("Native messaging host started")
        
        while self.running:
            message = self.read_message()
            if message is None:
                break
            
            await self.handle_message(message)
        
        logger.info("Native messaging host stopped")

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.agent:
            self.agent.stop()
        if self.browser_context:
            await self.browser_context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()


async def main():
    host = NativeMessagingHost()
    try:
        await host.run()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        traceback.print_exc(file=sys.stderr)
    finally:
        await host.cleanup()


if __name__ == '__main__':
    asyncio.run(main())