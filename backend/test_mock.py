import asyncio
from cdp_use.client import CDPClient
from browser_use.browser.session_manager import SessionManager

async def main():
    # just testing if we can mock a method
    class MockTarget:
        async def getTargets(self):
            return {'targetInfos': [{'targetId': 'A', 'type': 'page'}, {'targetId': 'B', 'type': 'page'}]}
            
    class MockSend:
        def __init__(self):
            self.Target = MockTarget()
            
    class MockClient:
        def __init__(self):
            self.send = MockSend()
            
    client = MockClient()
    orig = client.send.Target.getTargets
    async def mock():
        res = await orig()
        res['targetInfos'] = [t for t in res['targetInfos'] if t['targetId'] == 'A']
        return res
        
    client.send.Target.getTargets = mock
    print(await client.send.Target.getTargets())

if __name__ == '__main__':
    asyncio.run(main())
