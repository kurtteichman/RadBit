import asyncio
from pydantic import BaseModel
from agents import (
    Agent,
    Runner,
    input_guardrail,
    GuardrailFunctionOutput,
    RunContextWrapper,
    TResponseInputItem
)

class SupportResponse(BaseModel):
    department: str
    phone: str
    email: str
    other: str
    note: str
    hours: str
    email_draft: str

class DepartmentLabel(BaseModel):
    department: str

class OutOfScopeCheck(BaseModel):
    is_off_topic: bool
    explanation: str

email_draft_agent = Agent(
    name="Email Draft Generator",
    instructions="""
    Write a conversational, polite email summarizing the user's issue.
    Use a human tone: open with a neutral greeting like 'To whom it may concern' if no specific name is provided.
    Include what happened, any steps they've already taken, and a request for help.
    Close with something friendly like 'Thank you' and sign as '[Your Name]'.
    Avoid headings, bullet points, or formal report formatting.
    """,
    model="gpt-4o"
)

guardrail_filter_agent = Agent(
    name="Out-of-Scope Filter",
    instructions="""
    Determine if the user’s message is off-topic for a radiology or IT support system.
    Mark it as off-topic if it involves philosophical, spiritual, existential, cosmic, or abstract questions 
    (e.g., 'meaning of life', 'is there a god', 'are we in a simulation').
    Only mark it in-scope if it clearly relates to technical, clinical, or IT issues relevant to radiologists or hospital staff.
    """,
    output_type=OutOfScopeCheck,
    model="gpt-4o"
)

@input_guardrail
async def radiology_scope_guardrail(
    ctx: RunContextWrapper[None], agent: Agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    result = await Runner.run(guardrail_filter_agent, input, context=ctx.context)
    return GuardrailFunctionOutput(
        output_info=result.final_output,
        tripwire_triggered=result.final_output.is_off_topic
    )

hospital_rr_agent = Agent(
    name="Hospital Reading Rooms Agent",
    instructions="Route clinical PACS/viewer issues during image interpretation (CT/MRI freezing, crashes).",
    model="gpt-4o"
)

virtual_helpdesk_agent = Agent(
    name="Virtual HelpDesk Agent",
    instructions="Route general in-hospital desktop login or certificate issues, Zoom support available.",
    model="gpt-4o"
)

wcinyp_agent = Agent(
    name="WCINYP IT Agent",
    instructions="Route remote/home access issues: VPN, Outlook, EPIC, or other systems not at hospital.",
    model="gpt-4o"
)

radiqal_agent = Agent(
    name="Radiqal Agent",
    instructions="Route QA/discrepancy reports (image labels, mismatches) needing Radiqal tool via PACS.",
    model="gpt-4o"
)

SUPPORT_DIRECTORY = {
    "Hospital Reading Rooms": {
        "phone": "4-HELP (4-4357) or (212) 932-4357",
        "email": "servicedesk@nyp.org (Subject: RADSUPPORTEASTCRITICAL)",
        "other": "N/A",
        "note": "Clinical PACS workstation support",
        "hours": "24/7"
    },
    "Virtual HelpDesk": {
        "phone": "(212) 746-4878",
        "email": "N/A",
        "other": "Zoom: https://nyph.zoom.us/j/9956909465",
        "note": "Support via Zoom sessions",
        "hours": "Mon–Fri, 9 AM–5 PM"
    },
    "WCINYP IT": {
        "phone": "(212) 746-4878",
        "email": "wcinypit@med.cornell.edu",
        "other": "Contact via myHelpdesk portal 24/7",
        "note": "Home VPN / EPIC / Outlook issues",
        "hours": "7 AM–7 PM"
    },
    "Radiqal": {
        "phone": "N/A",
        "email": "N/A - use Radiqal within Medicalis/VuePACS",
        "other": "Use Radiqal Tip Sheet guidance",
        "note": "QA system support",
        "hours": "Platform dependent"
    },
}

triage_agent = Agent(
    name="Support Triage Agent",
    instructions="""
    Based on the user's description, pick exactly one department:
    - Hospital Reading Rooms: PACS/image viewer freezing or crashes during CT/MRI interpretation.
    - Virtual HelpDesk: In-hospital desktop login, certificate, or workstation issues (not PACS).
    - WCINYP IT: Remote/home issues — VPN, Outlook, EPIC, email sync.
    - Radiqal: QA/discrepancy reports via Radiqal in Medicalis/VuePACS.

    Respond with JSON: {"department": "Hospital Reading Rooms"}
    """,
    output_type=DepartmentLabel,
    handoffs=[hospital_rr_agent, virtual_helpdesk_agent, wcinyp_agent, radiqal_agent],
    model="gpt-4o",
    input_guardrails=[radiology_scope_guardrail]
)

def run_async_task(task):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(task)

def triage_and_get_support_info(user_input: str) -> SupportResponse:
    triage_result = run_async_task(Runner.run(triage_agent, user_input))
    dept = triage_result.final_output.department

    if dept not in SUPPORT_DIRECTORY:
        raise ValueError(f"Unknown department returned: {dept}")

    contact = SUPPORT_DIRECTORY[dept]
    draft = run_async_task(Runner.run(email_draft_agent, user_input))

    return SupportResponse(
        department=dept,
        phone=contact["phone"],
        email=contact["email"],
        other=contact["other"],
        note=contact["note"],
        hours=contact["hours"],
        email_draft=draft.final_output
    )
