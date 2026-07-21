import inspect
import asyncio
from browser_use.browser.browser import Browser

async def main():
    browser = Browser(cdp_url="http://localhost:9222")
    # we don't really want to connect to a real browser, but we can inspect the module if we find it
    import importlib
    for m in ["browser_use.cdp", "browser_use.browser.cdp", "browser_use.utils.cdp"]:
        try:
            print("Trying", m)
            mod = importlib.import_module(m)
            print("Found", m, mod)
        except ImportError:
            pass

if __name__ == "__main__":
    asyncio.run(main())
