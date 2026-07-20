import pydantic
from pydantic import BaseModel, Field
import re

class A(BaseModel):
    pass

@classmethod
def new_validate(cls, json_data, *args, **kwargs):
    print("Cleaned!")
    # Simulate cleaning
    match = re.search(r'\{.*\}', json_data, re.DOTALL)
    if match:
        json_data = match.group(0)
    return super(A, cls).model_validate_json(json_data, *args, **kwargs)

A.model_validate_json = new_validate

class B(A):
    name: str = Field(..., description="name")

# Try validating B with extra fields and dirty string
try:
    # B has fields, if it validates correctly it will have name
    b = B.model_validate_json('dirty text before {"name": "test"} and after')
    print("B parsed:", b)
except Exception as e:
    print("Error:", e)
