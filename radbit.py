import asyncio
import json
from datetime import datetime
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
    warning: str | None = None
    fallback_department: str | None = None

class DepartmentLabel(BaseModel):
    department: str

class OutOfScopeCheck(BaseModel):
    is_off_topic: bool
    explanation: str

email_draft_agent = Agent(
    name="Email Draft Generator",
    instructions="""
    Write a polite, conversational email based on the user's issue and metadata.
    Greet with "To whom it may concern" if no specific name is given.
    Mention what happened, steps already taken, and what help is being sought.
    Close with "Thank you" and sign with the user's name (given in metadata).
    No headings or bullet points — just a simple email format.
    """,
    model="gpt-4o"
)

guardrail_filter_agent = Agent(
    name="Out-of-Scope Filter",
    instructions="""
    Flag philosophical or abstract questions (e.g., meaning of life, existence) as off-topic.
    Only allow clinical/technical radiology or hospital-related support issues.
    """,
    output_type=OutOfScopeCheck,
    model="gpt-4o"
)

@input_guardrail
async def radiology_scope_guardrail(ctx: RunContextWrapper[None], agent: Agent, input: str | list[TResponseInputItem]) -> GuardrailFunctionOutput:
    result = await Runner.run(guardrail_filter_agent, input, context=ctx.context)
    return GuardrailFunctionOutput(
        output_info=result.final_output,
        tripwire_triggered=result.final_output.is_off_topic
    )

hospital_rr_agent = Agent(name="Hospital Reading Rooms Agent", instructions="Handle PACS/viewer issues during image interpretation.", model="gpt-4o")
virtual_helpdesk_agent = Agent(name="Virtual HelpDesk Agent", instructions="In-hospital desktop login/certificates, Zoom help.", model="gpt-4o")
wcinyp_agent = Agent(name="WCINYP IT Agent", instructions="Remote access: VPN, Outlook, EPIC, etc.", model="gpt-4o")
radiqal_agent = Agent(name="Radiqal Agent", instructions="QA issues with Radiqal in PACS/Medicalis.", model="gpt-4o")

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
    Based on the user's description and metadata, choose one department:
    - Hospital Reading Rooms: Viewer freezing, crashes.
    - Virtual HelpDesk: In-hospital certificate/login issues.
    - WCINYP IT: Remote workstation, VPN, Outlook problems.
    - Radiqal: QA or discrepancy reports.

    Reply with JSON: {"department": "Hospital Reading Rooms"}
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

def parse_hours_to_range(hours: str):
    if hours.strip() == "24/7":
        return None
    import re
    match = re.search(r"(\d{1,2})(?:\s*AM)?–(\d{1,2})(?:\s*PM)?", hours)
    if match:
        start_hour = int(match.group(1))
        end_hour = int(match.group(2)) + 12 if int(match.group(2)) < 12 else int(match.group(2))
        return start_hour, end_hour
    return None

def triage_and_get_support_info(user_input: str, backend_json: dict) -> SupportResponse:
    combined_input = {
        "request": user_input,
        "metadata": backend_json
    }

    triage_result = run_async_task(Runner.run(triage_agent, combined_input))
    dept = triage_result.final_output.department
    contact = SUPPORT_DIRECTORY.get(dept)
    if not contact:
        raise ValueError(f"Unknown department returned: {dept}")

    now = datetime.now()
    warning = None
    fallback = None

    hours_range = parse_hours_to_range(contact["hours"])
    if hours_range:
        if not (hours_range[0] <= now.hour < hours_range[1]):
            warning = f"{dept} is currently closed. Hours: {contact['hours']}."
            for alt_dept, alt_info in SUPPORT_DIRECTORY.items():
                if alt_dept != dept:
                    alt_hours_range = parse_hours_to_range(alt_info["hours"])
                    if alt_hours_range and alt_hours_range[0] <= now.hour < alt_hours_range[1]:
                        fallback = alt_dept
                        break

    name = backend_json.get("user", {}).get("name", "[Your Name]")
    draft_input = f"The following user ({name}) reports: {user_input}"
    draft = run_async_task(Runner.run(email_draft_agent, draft_input))

    return SupportResponse(
        department=dept,
        phone=contact["phone"],
        email=contact["email"],
        other=contact["other"],
        note=contact["note"],
        hours=contact["hours"],
        email_draft=draft.final_output,
        warning=warning,
        fallback_department=fallback
    )
