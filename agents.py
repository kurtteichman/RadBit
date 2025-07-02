import asyncio
from typing import Any, Optional, TypeVar, Generic

# Placeholder agent class
class Agent:
    def __init__(self, name: str, instructions: str, model: str = "gpt-4o", output_type: Optional[Any] = None,
                 input_guardrails: Optional[list] = None, handoffs: Optional[list] = None):
        self.name = name
        self.instructions = instructions
        self.model = model
        self.output_type = output_type
        self.input_guardrails = input_guardrails or []
        self.handoffs = handoffs or []

# Placeholder runner and result
T = TypeVar("T")

class RunContextWrapper(Generic[T]):
    context: Optional[T] = None

class GuardrailFunctionOutput:
    def __init__(self, output_info, tripwire_triggered: bool = False):
        self.output_info = output_info
        self.tripwire_triggered = tripwire_triggered

class RunResult:
    def __init__(self, final_output, last_used_agent=None):
        self.final_output = final_output
        self.last_used_agent = last_used_agent or Agent("Unknown", "", "gpt-4o")

class Runner:
    @staticmethod
    async def run(agent: Agent, input_data: Any, context: Any = None) -> RunResult:
        # Mock behavior: map input strings to dummy departments
        message = input_data.strip().lower()
        if "freeze" in message or "crash" in message:
            return RunResult(final_output=DummyLabel("Hospital Reading Rooms"), last_used_agent=agent)
        elif "login" in message or "certificate" in message:
            return RunResult(final_output=DummyLabel("Virtual HelpDesk"), last_used_agent=agent)
        elif "vpn" in message or "outlook" in message:
            return RunResult(final_output=DummyLabel("WCINYP IT"), last_used_agent=agent)
        elif "radiqal" in message or "label" in message:
            return RunResult(final_output=DummyLabel("Radiqal"), last_used_agent=agent)
        else:
            return RunResult(final_output=DummyLabel("Virtual HelpDesk"), last_used_agent=agent)

# Input and label scaffolding
class TResponseInputItem:
    pass

class DummyLabel:
    def __init__(self, department: str):
        self.department = department

# Guardrail decorator
def input_guardrail(func):
    async def wrapped(ctx: RunContextWrapper[None], agent: Agent, input_data: Any):
        return await func(ctx, agent, input_data)
    return wrapped

# Exception used in original app
class InputGuardrailTripwireTriggered(Exception):
    pass

# Dummy key setter
def set_default_openai_key(api_key: str):
    pass
