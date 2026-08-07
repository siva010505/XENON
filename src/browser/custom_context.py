import json
import logging
import os
from typing import Optional, List

from browser_use.browser.browser import Browser, IN_DOCKER
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import BrowserContext as PlaywrightBrowserContext
from playwright.async_api import Page, Frame, ElementHandle
from browser_use.browser.context import BrowserContextState
from browser_use.browser.views import BrowserState, BrowserStateHistory, TabInfo
from browser_use.dom.views import DOMElementNode, SelectorMap

logger = logging.getLogger(__name__)


class CustomBrowserContext(BrowserContext):
    def __init__(
            self,
            browser: 'Browser',
            config: BrowserContextConfig | None = None,
            state: Optional[BrowserContextState] = None,
    ):
        super(CustomBrowserContext, self).__init__(browser=browser, config=config, state=state)
        self._initialized = False
        if not hasattr(self, '_context'):
            self._context = None
        if not hasattr(self, '_connected_page'):
            self._connected_page = None

    async def _initialize(self) -> None:
        """Initialize the context. Override to handle existing page."""
        if self._initialized:
            return
            
        # If we already have a context (from CDP connection), use it
        if self._context is not None:
            self._initialized = True
            logger.info("Using existing Playwright context from CDP connection")
            return
            
        # Otherwise, create new context normally
        await self._initialize_session()
        self._initialized = True

    async def _resize_window(self, *args, **kwargs) -> None:
        """Override to prevent resizing/minimizing existing Chrome window when connected via CDP."""
        pass

    async def get_current_page(self) -> Page:
        """Get the current page. Override to return connected page."""
        await self._initialize()
        
        # If we have a cached page from CDP connection, verify it's still alive
        if hasattr(self, '_connected_page') and self._connected_page:
            try:
                if not self._connected_page.is_closed():
                    self.agent_current_page = self._connected_page
                    self.human_current_page = self._connected_page
                    try:
                        await self._connected_page.bring_to_front()
                    except Exception:
                        pass
                    return self._connected_page
            except Exception:
                pass
            
        # Otherwise get the first active web page from context
        if self._context and self._context.pages:
            for p in reversed(self._context.pages):
                try:
                    url = p.url or ""
                    if not url.startswith("chrome://") and not url.startswith("chrome-extension://") and not url.startswith("devtools://"):
                        self._connected_page = p
                        self.agent_current_page = p
                        self.human_current_page = p
                        return p
                except Exception:
                    continue
            page = self._context.pages[0]
            self.agent_current_page = page
            self.human_current_page = page
            return page
            
        raise RuntimeError("No browser context available")

    async def get_pages(self) -> List[Page]:
        """Get all pages in the context."""
        await self._initialize()
        if self._context:
            return self._context.pages
        return []

    async def get_state(self, use_vision: bool = True, cache_clickable_elements_hashes: bool = True) -> BrowserState:
        """Get browser state. Override to work with existing page."""
        await self._initialize()
        page = await self.get_current_page()
        
        # Get page info
        url = page.url
        title = await page.title()
        
        # Get tabs info
        tabs = []
        pages = await self.get_pages()
        for i, p in enumerate(pages):
            try:
                p_title = await p.title()
            except Exception:
                p_title = ""
            tabs.append(TabInfo(
                page_id=i,
                url=p.url,
                title=p_title
            ))
        
        # Get DOM state
        from browser_use.dom.service import DomService
        dom_service = DomService(page)
        dom_state = await dom_service.get_clickable_elements()
        
        selector_map = dom_state.selector_map
        element_tree = dom_state.element_tree
        
        # Get screenshot if vision enabled
        screenshot = None
        if use_vision:
            try:
                # Ensure edge light is injected for human eyes on live tab
                await self.inject_edge_light(page)

                # Temporarily hide edge light right before capturing screenshot for Vision model
                try:
                    await page.evaluate('''() => {
                        const el = document.getElementById('bu-agent-edge-light');
                        if (el) el.style.display = 'none';
                    }''')
                except Exception:
                    pass

                screenshot_bytes = await page.screenshot(full_page=False, type='jpeg', quality=75)
                import base64
                screenshot = base64.b64encode(screenshot_bytes).decode('utf-8')

                # Immediately restore edge light for human eyes on live tab after screenshot capture
                await self.inject_edge_light(page)
            except Exception as e:
                logger.debug(f"Failed to capture screenshot: {e}")
        
        # Flash-and-Remove: Clean highlights from live Chrome tab immediately after screenshot capture
        try:
            await page.evaluate('''() => {
                try {
                    const c1 = document.getElementById('playwright-highlight-container');
                    if (c1) c1.remove();
                    const c2 = document.getElementById('browser-use-highlight-container');
                    if (c2) c2.remove();
                    const highlightedElements = document.querySelectorAll('[browser-user-highlight-id]');
                    highlightedElements.forEach(el => el.removeAttribute('browser-user-highlight-id'));
                } catch(e) {}
            }''')
        except Exception as rh_err:
            logger.debug(f"Failed to remove highlights: {rh_err}")
        
        state = BrowserState(
            url=url,
            title=title,
            tabs=tabs,
            selector_map=selector_map,
            element_tree=element_tree,
            screenshot=screenshot,
            pixels_above=0,
            pixels_below=0,
        )
        
        # Update session.cached_state so Controller.get_selector_map() accesses the new DOM tree!
        session = await self.get_session()
        session.cached_state = state
        return state

    async def inject_edge_light(self, page: Page) -> None:
        """Inject mild neon blue edge light animation on active working tab."""
        try:
            if not page or page.is_closed():
                return
            url = page.url or ""
            if url.startswith("chrome://") or url.startswith("chrome-extension://") or url.startswith("devtools://"):
                return
            await page.evaluate('''() => {
                try {
                    let el = document.getElementById('bu-agent-edge-light');
                    if (!el) {
                        el = document.createElement('div');
                        el.id = 'bu-agent-edge-light';
                        el.style.cssText = `
                            position: fixed !important;
                            top: 0 !important;
                            left: 0 !important;
                            width: 100vw !important;
                            height: 100vh !important;
                            pointer-events: none !important;
                            z-index: 2147483647 !important;
                            box-sizing: border-box !important;
                            border: 2.5px solid #00c6ff !important;
                            box-shadow: inset 0 0 20px 4px rgba(0, 194, 255, 0.75), 0 0 15px 3px rgba(0, 102, 255, 0.65) !important;
                            animation: buEdgePulse 2s ease-in-out infinite !important;
                            margin: 0 !important;
                            padding: 0 !important;
                        `;
                        let style = document.getElementById('bu-agent-edge-light-style');
                        if (!style) {
                            style = document.createElement('style');
                            style.id = 'bu-agent-edge-light-style';
                            style.textContent = `
                                @keyframes buEdgePulse {
                                    0%, 100% { opacity: 0.9; box-shadow: inset 0 0 22px 5px rgba(0, 210, 255, 0.8), 0 0 18px 4px rgba(0, 102, 255, 0.7); border-color: #00c6ff; }
                                    50% { opacity: 0.5; box-shadow: inset 0 0 10px 2px rgba(0, 194, 255, 0.4), 0 0 8px 2px rgba(0, 102, 255, 0.35); border-color: #0072ff; }
                                }
                            `;
                            document.head.appendChild(style);
                        }
                        document.documentElement.appendChild(el);
                    } else {
                        el.style.display = 'block';
                    }
                } catch(e) {}
            }''')
        except Exception as e:
            logger.debug(f"Failed injecting edge light: {e}")

    async def remove_edge_light_from_all_pages(self) -> None:
        """Remove edge light overlays from all open pages in the context."""
        try:
            pages = await self.get_pages()
            for p in pages:
                try:
                    await p.evaluate('''() => {
                        const el = document.getElementById('bu-agent-edge-light');
                        if (el) el.remove();
                        const style = document.getElementById('bu-agent-edge-light-style');
                        if (style) style.remove();
                    }''')
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Failed cleaning all page edge lights: {e}")

    async def take_screenshot(self, full_page: bool = False) -> str:
        """Take screenshot of current page."""
        page = await self.get_current_page()
        # Temporarily hide edge light right before screenshot capture
        try:
            await page.evaluate('''() => {
                const el = document.getElementById('bu-agent-edge-light');
                if (el) el.style.display = 'none';
            }''')
        except Exception:
            pass

        screenshot_bytes = await page.screenshot(full_page=full_page, type='jpeg', quality=75)
        import base64
        screenshot = base64.b64encode(screenshot_bytes).decode('utf-8')

        # Restore edge light after screenshot
        await self.inject_edge_light(page)
        return screenshot

    async def remove_highlights_from_all_pages(self) -> None:
        """Remove highlight boxes from all open pages in the context."""
        try:
            pages = await self.get_pages()
            for p in pages:
                try:
                    await p.evaluate('''() => {
                        const c1 = document.getElementById('playwright-highlight-container');
                        if (c1) c1.remove();
                        const c2 = document.getElementById('browser-use-highlight-container');
                        if (c2) c2.remove();
                        const highlightedElements = document.querySelectorAll('[browser-user-highlight-id]');
                        highlightedElements.forEach(el => el.removeAttribute('browser-user-highlight-id'));
                    }''')
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Failed cleaning all page highlights: {e}")

    async def close(self) -> None:
        """Close context. Override to not close the connected browser."""
        # Don't close the browser if we're connected via CDP
        # Just clean up our references and remove leftover overlays
        await self.remove_highlights_from_all_pages()
        await self.remove_edge_light_from_all_pages()
        if hasattr(self, '_connected_page'):
            self._connected_page = None
        self._context = None
        self._initialized = False
        logger.info("CustomBrowserContext closed (kept CDP connection alive)")

    async def switch_to_tab(self, page_id: int) -> None:
        """Switch to a tab by 0-based index and update connected page reference."""
        pages = await self.get_pages()
        if page_id < 0 or page_id >= len(pages):
            raise ValueError(f"No tab found with page_id: {page_id}")
        
        target_page = pages[page_id]
        self._connected_page = target_page
        self.agent_current_page = target_page
        self.human_current_page = target_page
        try:
            await target_page.bring_to_front()
        except Exception as e:
            logger.debug(f"Could not bring page to front: {e}")
            
    async def _click_element_node(self, element_node) -> str | None:
        """Enhanced click method that triggers direct JS anchor clicks on SPA grid links (Instagram, Youtube Shorts, Amazon)."""
        try:
            page = await self.get_agent_current_page()
            element_handle = await self.get_locate_element(element_node)
            if element_handle:
                # If element is an <a> tag or inside an <a> tag, trigger direct anchor JS click to bypass overlay interception
                clicked_link = await page.evaluate('''el => {
                    if (!el) return false;
                    const anchor = el.tagName === 'A' ? el : el.closest('a');
                    if (anchor && anchor.href && !anchor.href.startsWith('javascript:')) {
                        anchor.click();
                        return true;
                    }
                    return false;
                }''', element_handle)
                if clicked_link:
                    logger.info(f"Triggered direct JS anchor click for index {element_node.highlight_index}")
                    try:
                        await page.wait_for_load_state('domcontentloaded', timeout=2000)
                    except Exception:
                        pass
                    return None
        except Exception as e:
            logger.debug(f"Direct anchor click evaluation: {e}")

        return await super()._click_element_node(element_node)

    def set_connected_page(self, page: Page) -> None:
        """Set the connected page from CDP attachment."""
        self._connected_page = page
        self.agent_current_page = page
        self.human_current_page = page
        if page and page.context:
            self._context = page.context
            self._initialized = True