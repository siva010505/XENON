import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv()

class ActionModel(BaseModel):
    action: str = Field(description="The action to take")
    reasoning: str = Field(description="Why you took this action")

llm = ChatOpenAI(
    model="meta/llama-3.3-70b-instruct",
    api_key=os.getenv("NVIDIA_API_KEY"),
    base_url="https://integrate.api.nvidia.com/v1"
)

# Test if bind_tools works
llm_with_tools = llm.bind_tools([ActionModel])

try:
    print("Invoking model with bind_tools...")
    res = llm_with_tools.invoke("Search AWS and give me the reasoning.")
    print("\nResult properties:")
    print("Content:", res.content)
    print("Tool calls:", res.tool_calls)
except Exception as e:
    import traceback
    traceback.print_exc()
