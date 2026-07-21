import sys
import gc

try:
    from browser_use.browser.session import BrowserSession
except ImportError:
    pass
try:
    from browser_use.browser.browser import Browser
except ImportError:
    pass

def find_target_client():
    for obj in gc.get_objects():
        if type(obj).__name__ == 'type' and obj.__name__ == 'TargetClient':
            print("Found TargetClient in module:", obj.__module__)
            import inspect
            print("Signature of closeTarget:", inspect.signature(obj.closeTarget))
            return
    print("TargetClient not found in memory")

find_target_client()
