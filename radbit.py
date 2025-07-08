import asyncio
import json
from datetime import datetime
from pydantic import BaseModel
from openai import OpenAI
from agents import (
    Agent,
    Runner,
    input_guardrail,
    GuardrailFunctionOutput,
    RunContextWrapper,
    TResponseInputItem,
)
import holidays

_BACKEND_EXAMPLE_INDEX = 2
_client = OpenAI()

class SupportResponse(BaseModel):
    department: str
    phone: str
    email: str
    other: str
    note: str
    hours: str
    email_draft: str
    support_available: bool = True
    fallback_department: str | None = None

class DepartmentLabel(BaseModel):
    department: str

class OutOfScopeCheck(BaseModel):
    is_off_topic: bool
    explanation: str

guardrail_filter_agent = Agent(
    name="Out-of-Scope Filter",
    instructions="""
Determine if the user's message is off-topic (philosophical, existential, etc.).
Only allow clear radiology/IT support requests through.
""",
    output_type=OutOfScopeCheck,
    model="gpt-4o",
)

@input_guardrail
async def radiology_scope_guardrail(
    ctx: RunContextWrapper[None],
    agent: Agent,
    input: str | list[TResponseInputItem],
) -> GuardrailFunctionOutput:
    out = await Runner.run(guardrail_filter_agent, input, context=ctx.context)
    return GuardrailFunctionOutput(
        output_info=out.final_output,
        tripwire_triggered=out.final_output.is_off_topic,
    )

hospital_rr_agent = Agent(
    name="Hospital Reading Rooms Agent",
    instructions="Handle clinical PACS/viewer crashes or freezes during CT/MRI interpretation.",
    model="gpt-4o",
)
virtual_helpdesk_agent = Agent(
    name="Virtual HelpDesk Agent",
    instructions="Handle in-hospital desktop/login or certificate issues; Zoom support available.",
    model="gpt-4o",
)
wcinyp_agent = Agent(
    name="WCINYP IT Agent",
    instructions="Handle remote/home issues: VPN, Outlook, EPIC, email sync.",
    model="gpt-4o",
)
radiqal_agent = Agent(
    name="Radiqal Agent",
    instructions="Handle QA/discrepancy tickets via Radiqal within PACS.",
    model="gpt-4o",
)

triage_agent = Agent(
    name="Support Triage Agent",
    instructions="""
Based on the user's description and context (subspecialty, time, location),
choose exactly one department. Reply ONLY with JSON like:
{"department": "Hospital Reading Rooms"}
""",
    output_type=DepartmentLabel,
    handoffs=[hospital_rr_agent, virtual_helpdesk_agent, wcinyp_agent, radiqal_agent],
    model="gpt-4o",
    input_guardrails=[radiology_scope_guardrail],
)
SUPPORT_DIRECTORY = {
    "Hospital Reading Rooms": {
        "phone": "4-HELP (4-4357) or (212) 932-4357",
        "email": "servicedesk@nyp.org (Subject: RADSUPPORTEASTCRITICAL)",
        "other": "N/A",
        "note": "Clinical PACS workstation support",
        "hours": "24/7",
    },
    "Virtual HelpDesk": {
        "phone": "(212) 746-4878",
        "email": "N/A",
        "other": "Zoom: https://nyph.zoom.us/j/9956909465",
        "note": "Support via Zoom sessions",
        "hours": "Mon–Fri, 9 AM–5 PM",
    },
    "WCINYP IT": {
        "phone": "4-HELP (212-746-4357)",
        "email": "Normal (24/7): nypradtickets@nyp.org | On-Call (5PM–8AM): nypradoncall@nyp.org",
        "other": "Zoom (M–F, 9–5): https://nyph.zoom.us/j/9956909465",
        "note": "Vue PACS, Medicalis, Fluency, Diagnostic Workstations, Radiology Systems Support",
        "hours": "24/7",
    },
    "Radiqal": {
        "phone": "N/A",
        "email": "N/A - use Radiqal within Medicalis/VuePACS",
        "other": "Use Radiqal Tip Sheet guidance",
        "note": "QA system support",
        "hours": "Platform dependent",
    },
}
