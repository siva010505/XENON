import asyncio
from browser_use.agent.views import AgentOutput
from browser_use.agent.service import Agent
from browser_use.llm.openai.chat import ChatOpenAI

async def main():
    agent = Agent(task='', llm=ChatOpenAI(model='gpt-3.5-turbo'))
    ActionModel = agent.ActionModel
    
    try:
        obj = ActionModel.model_validate_json('{"switch": {"tab_id": "B3C9"}}')
        print("ActionModel matched:", obj)
    except Exception as e:
        print("ActionModel error:", type(e), str(e))
        
    json_str = '{"evaluation_previous_goal": "x", "memory": "x", "next_goal": "x", "action": [{"switch": {"tab_id": "B3C9"}}]}'
    try:
        AgentOutput.model_validate_json(json_str)
        print("AgentOutput Success!")
    except Exception as e:
        print("AgentOutput Error:", type(e), str(e))

if __name__ == '__main__':
    asyncio.run(main())
