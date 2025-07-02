from typing import Any, Callable, Awaitable, Union, List
from pydantic import BaseModel


class TResponseInputItem(BaseModel):
    type: str
    content: Any


class GuardrailFunctionOutput(BaseModel):
    output_info: Any
    tripwire_triggered: bool


class RunContextWrapper(BaseModel):
    context: dict[str, Any] = {}


class Agent(BaseModel):
    name: str
    instructions: str
    model: str
    output_type: type = None
    handoffs: list["Agent"] = []
    input_guardrails: list[Callable[..., Awaitable[GuardrailFunctionOutput]]] = []

    class Config:
        arbitrary_types_allowed = True


class Runner:
    @staticmethod
    async def run(agent: Agent, input_data: Union[str, List[TResponseInputItem]], context: dict = None):
        # Mock behavior: simulate the output object that has .final_output
        class Result:
            def __init__(self):
                self.final_output = type("Output", (), {"department": "WCINYP IT", "__str__": lambda self: "WCINYP IT"})()

        return Result()


def input_guardrail(func):
    # Decorator placeholder
    return func
