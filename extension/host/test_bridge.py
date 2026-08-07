"""
Test CDP connection from Python - run this to verify bridge can connect to Chrome.
"""
import sys
sys.path.insert(0, 'C:\\Users\\acer\\OneDrive - ELCOT\\AUTO')
import asyncio
import traceback
from extension.host.bridge import NativeMessagingHost

async def test():
    host = NativeMessagingHost()
    try:
        connected = await host.connect_to_cdp('http://localhost:9222')
        print(f'CDP connected: {connected}')
        if connected:
            print('SUCCESS - Bridge can connect to Chrome')
        else:
            print('FAILED - Bridge cannot connect to Chrome CDP')
            print('Make sure Chrome is running with --remote-debugging-port=9222')
    except Exception as e:
        print(f'ERROR: {e}')
        traceback.print_exc()
    finally:
        await host.cleanup()

if __name__ == '__main__':
    asyncio.run(test())