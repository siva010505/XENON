from browser_use.agent.views import AgentOutput
from browser_use.agent.service import Agent
from browser_use.llm.openai.chat import ChatOpenAI
import asyncio

async def main():
    agent = Agent(task='', llm=ChatOpenAI(model='gpt-3.5-turbo'))
    # the ActionModel is instantiated dynamically when Agent initializes
    # wait, AgentOutput is dynamically generated based on ActionModel!
    # Let's inspect AgentOutput
    try:
        agent.ActionModel.model_validate_json('{"click_element": {"index": 2117}}')
        print("ActionModel validation passed.")
    except Exception as e:
        print("ActionModel error:", type(e), str(e))
        
    try:
        AgentOutput.model_validate_json('{"current_state": {"evaluation_previous_goal": "x", "memory": "x", "next_goal": "x"}, "action": [{"click_element": {"index": 2117}}]}')
        print("AgentOutput validation passed.")
    except Exception as e:
        print("AgentOutput error:", type(e), str(e))

if __name__ == '__main__':
    asyncio.run(main())
