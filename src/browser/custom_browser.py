import asyncio
import pdb
import json

from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import (
    BrowserContext as PlaywrightBrowserContext,
    Page,
)
from playwright.async_api import (
    Playwright,
    async_playwright,
)
from browser_use.browser.browser import Browser, IN_DOCKER
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from playwright.async_api import BrowserContext as PlaywrightBrowserContext
import logging

from browser_use.browser.chrome import (
    CHROME_ARGS,
    CHROME_DETERMINISTIC_RENDERING_ARGS,
    CHROME_DISABLE_SECURITY_ARGS,
    CHROME_DOCKER_ARGS,
    CHROME_HEADLESS_ARGS,
)
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.browser.utils.screen_resolution import get_screen_resolution, get_window_adjustments
from browser_use.utils import time_execution_async
import socket

from .custom_context import CustomBrowserContext

logger = logging.getLogger(__name__)


class CustomBrowser(Browser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._playwright_browser: PlaywrightBrowser | None = None
        self._cdp_session = None
        self._connected_page: Page | None = None

    async def new_context(self, config: BrowserContextConfig | None = None) -> CustomBrowserContext:
        """Create a browser context"""
        browser_config = self.config.model_dump() if self.config else {}
        context_config = config.model_dump() if config else {}
        merged_config = {**browser_config, **context_config}
        return CustomBrowserContext(config=BrowserContextConfig(**merged_config), browser=self)

    async def get_playwright_browser(self) -> PlaywrightBrowser:
        """Get the playwright browser instance. Returns existing CDP connected browser if available."""
        if hasattr(self, '_playwright_browser') and self._playwright_browser:
            self.playwright_browser = self._playwright_browser
            return self._playwright_browser
        if hasattr(self, 'playwright_browser') and self.playwright_browser:
            return self.playwright_browser
        return await self._init()

    async def connect_over_cdp(self, cdp_url: str, target_page_url: str | None = None) -> CustomBrowserContext:
        """
        Connect to an existing Chrome instance via CDP and attach to a specific tab.
        
        Args:
            cdp_url: CDP HTTP URL (e.g., http://localhost:9222)
            target_page_url: Optional URL of the tab to attach to. If None, uses first available tab.
        
        Returns:
            CustomBrowserContext connected to the existing tab
        """
        logger.info(f"Connecting to Chrome via CDP: {cdp_url}")
        
        # Start playwright if not already started
        if not hasattr(self, '_playwright') or self._playwright is None:
            self._playwright = await async_playwright().start()
        
        # Reuse existing connected browser if still active, otherwise connect with 4s timeout or launch fallback
        is_connected = False
        if hasattr(self, '_playwright_browser') and self._playwright_browser:
            try:
                if self._playwright_browser.is_connected():
                    is_connected = True
            except Exception:
                is_connected = False

        if not is_connected:
            try:
                ipv4_cdp = cdp_url.replace("localhost", "127.0.0.1")
                self._playwright_browser = await self._playwright.chromium.connect_over_cdp(ipv4_cdp, timeout=12000)
                self.playwright_browser = self._playwright_browser
                logger.info("Successfully connected to Chrome via CDP")
            except Exception as cdp_err:
                logger.warning(f"CDP connection to {cdp_url} failed ({cdp_err}). Retrying CDP connection over IPv4...")
                try:
                    http_url = cdp_url.replace("localhost", "127.0.0.1")
                    self._playwright_browser = await self._playwright.chromium.connect_over_cdp(http_url, timeout=5000)
                    self.playwright_browser = self._playwright_browser
                    logger.info("Successfully reconnected to Chrome via CDP")
                except Exception as retry_err:
                    raise RuntimeError(f"Could not connect to Chrome over CDP ({cdp_url}): {retry_err}. Please verify Chrome is open and running with --remote-debugging-port=9222.") from retry_err
            
        logger.info(f"Connected to browser, contexts: {len(self._playwright_browser.contexts)}")
        
        # Find target page (prefer non-internal, non-extension web pages)
        target_page = None
        if target_page_url and not target_page_url.startswith("chrome://"):
            for context in self._playwright_browser.contexts:
                for page in context.pages:
                    if target_page_url in (page.url or ""):
                        target_page = page
                        break
                if target_page:
                    break

        if not target_page:
            for context in self._playwright_browser.contexts:
                for page in context.pages:
                    url = page.url or ""
                    if not url.startswith("chrome://") and not url.startswith("chrome-extension://") and not url.startswith("devtools://"):
                        target_page = page
                        break
                if target_page:
                    break
        
        if not target_page:
            for context in self._playwright_browser.contexts:
                if context.pages:
                    target_page = context.pages[0]
                    break

        if not target_page:
            if not self._playwright_browser.contexts:
                ctx = await self._playwright_browser.new_context()
            else:
                ctx = self._playwright_browser.contexts[0]
            target_page = await ctx.new_page()
        
        self._connected_page = target_page
        try:
            await target_page.bring_to_front()
        except Exception as btf_err:
            logger.debug(f"Could not bring page to front: {btf_err}")
            
        logger.info(f"Attached to page: {target_page.url}")
        
        # Create context config with no_viewport to preserve full screen Chrome window
        context_config = BrowserContextConfig(
            trace_path=None,
            save_recording_path=None,
            save_downloads_path="./tmp/downloads",
            no_viewport=True,
        )
        
        # Create custom context wrapping existing page
        browser_context = CustomBrowserContext(
            browser=self,
            config=context_config
        )
        browser_context.set_connected_page(target_page)
        browser_context._cached_state = None
        
        return browser_context

    async def _setup_builtin_browser(self, playwright: Playwright) -> PlaywrightBrowser:
        """Sets up and returns a Playwright Browser instance with anti-detection measures."""
        assert self.config.browser_binary_path is None, 'browser_binary_path should be None if trying to use the builtin browsers'

        # Use the configured window size from new_context_config if available
        if (
                not self.config.headless
                and hasattr(self.config, 'new_context_config')
                and hasattr(self.config.new_context_config, 'window_width')
                and hasattr(self.config.new_context_config, 'window_height')
        ):
            screen_size = {
                'width': self.config.new_context_config.window_width,
                'height': self.config.new_context_config.window_height,
            }
            offset_x, offset_y = get_window_adjustments()
        elif self.config.headless:
            screen_size = {'width': 1920, 'height': 1080}
            offset_x, offset_y = 0, 0
        else:
            screen_size = get_screen_resolution()
            offset_x, offset_y = get_window_adjustments()

        chrome_args = {
            f'--remote-debugging-port={self.config.chrome_remote_debugging_port}',
            *CHROME_ARGS,
            *(CHROME_DOCKER_ARGS if IN_DOCKER else []),
            *(CHROME_HEADLESS_ARGS if self.config.headless else []),
            *(CHROME_DISABLE_SECURITY_ARGS if self.config.disable_security else []),
            *(CHROME_DETERMINISTIC_RENDERING_ARGS if self.config.deterministic_rendering else []),
            f'--window-position={offset_x},{offset_y}',
            f'--window-size={screen_size["width"]},{screen_size["height"]}',
            *self.config.extra_browser_args,
        }

        # check if chrome remote debugging port is already taken,
        # if so remove the remote-debugging-port arg to prevent conflicts
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', self.config.chrome_remote_debugging_port)) == 0:
                chrome_args.remove(f'--remote-debugging-port={self.config.chrome_remote_debugging_port}')

        browser_class = getattr(playwright, self.config.browser_class)
        args = {
            'chromium': list(chrome_args),
            'firefox': [
                *{
                    '-no-remote',
                    *self.config.extra_browser_args,
                }
            ],
            'webkit': [
                *{
                    '--no-startup-window',
                    *self.config.extra_browser_args,
                }
            ],
        }

        browser = await browser_class.launch(
            channel='chromium',  # https://github.com/microsoft/playwright/issues/33566
            headless=self.config.headless,
            args=args[self.config.browser_class],
            proxy=self.config.proxy.model_dump() if self.config.proxy else None,
            handle_sigterm=False,
            handle_sigint=False,
        )
        return browser


