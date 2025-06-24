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
import holidays

BACKEND_EXAMPLE_INDEX = 2 

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

email_draft_agent = Agent(
    name="Email Draft Generator",
    instructions="""
    Write a conversational, polite email summarizing the user's issue.
    Use a human tone: open with a neutral greeting like 'To whom it may concern' if no specific name is provided.
    Include what happened, any steps they've already taken, and a request for help.
    Close with something friendly like 'Thank you' and sign as '{user_name}'.
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
    Based on the user's description and context (e.g., radiologist subspecialty, time, location), 
    pick exactly one department:
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

def parse_hours_string(hours_string):
    if hours_string.strip() == "24/7":
        return ("00:00", "23:59")
    if "–" in hours_string:
        times = hours_string.split("–")
        try:
            start = datetime.strptime(times[0].strip().replace(" ", ""), "%I%p").strftime("%H:%M")
            end = datetime.strptime(times[1].strip().replace(" ", ""), "%I%p").strftime("%H:%M")
            return (start, end)
        except:
            return None
    return None

def load_backend_json(path="fake_backend_data.json", index=BACKEND_EXAMPLE_INDEX):
    with open(path, "r") as f:
        examples = json.load(f)
    return examples[index]

def triage_and_get_support_info(user_input: str) -> SupportResponse:
    backend = load_backend_json()
    name = backend["user"]["name"]
    time_str = backend["timestamp"]["time"]
    date_str = backend["timestamp"]["date"]
    day_of_week = backend["timestamp"]["day_of_week"]
    is_weekend_or_holiday = backend["timestamp"]["is_weekend_or_holiday"].lower() == "yes"

    triage_result = run_async_task(Runner.run(triage_agent, user_input))
    dept = triage_result.final_output.department
    contact = SUPPORT_DIRECTORY[dept]

    support_available = True
    fallback = None

    if contact["hours"].strip() != "24/7":
        time_range = parse_hours_string(contact["hours"])
        try:
            now = datetime.strptime(time_str.split()[0], "%H:%M:%S")
        except:
            now = datetime.strptime("12:00:00", "%H:%M:%S")
        start = datetime.strptime(time_range[0], "%H:%M")
        end = datetime.strptime(time_range[1], "%H:%M")

        us_holidays = holidays.US()
        is_holiday = date_str in us_holidays

        if not (start <= now <= end) or day_of_week in ["Sat", "Sun"] or is_weekend_or_holiday or is_holiday:
            support_available = False
            for alt_dept, details in SUPPORT_DIRECTORY.items():
                if alt_dept != dept and details["hours"].strip() != "24/7":
                    range_ = parse_hours_string(details["hours"])
                    alt_start, alt_end = datetime.strptime(range_[0], "%H:%M"), datetime.strptime(range_[1], "%H:%M")
                    if alt_start <= now <= alt_end:
                        fallback = alt_dept
                        break

    draft_prompt = user_input + f" Please sign the email as {name}."
    draft = run_async_task(Runner.run(email_draft_agent, draft_prompt))

    return SupportResponse(
        department=dept,
        phone=contact["phone"],
        email=contact["email"],
        other=contact["other"],
        note=contact["note"],
        hours=contact["hours"],
        email_draft=draft.final_output,
        support_available=support_available,
        fallback_department=fallback
    )
