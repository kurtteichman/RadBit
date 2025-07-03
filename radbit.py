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
    TResponseInputItem,
)
import holidays

BACKEND_EXAMPLE_INDEX = 2  # set to 0, 1, or 2 to pick the JSON entry

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
Use a human tone, opening with 'To whom it may concern' if no name is known.
Include what happened, any steps taken, and a request for help.
Close with 'Thank you' and sign as '{user_name}'.
Avoid bullet lists or formal report style.
""",
    model="gpt-4o"
)

guardrail_filter_agent = Agent(
    name="Out-of-Scope Filter",
    instructions="""
Determine if the user's message is off-topic (philosophical, existential, etc.).
Only allow through clear radiology/IT support requests.
""",
    output_type=OutOfScopeCheck,
    model="gpt-4o"
)

@input_guardrail
async def radiology_scope_guardrail(
    ctx: RunContextWrapper[None],
    agent: Agent,
    input: str | list[TResponseInputItem],
) -> GuardrailFunctionOutput:
    result = await Runner.run(guardrail_filter_agent, input, context=ctx.context)
    return GuardrailFunctionOutput(
        output_info=result.final_output,
        tripwire_triggered=result.final_output.is_off_topic,
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
        "phone": "(212) 746-4878",
        "email": "wcinypit@med.cornell.edu",
        "other": "Contact via myHelpdesk portal 24/7",
        "note": "Home VPN / EPIC / Outlook issues",
        "hours": "7 AM–7 PM",
    },
    "Radiqal": {
        "phone": "N/A",
        "email": "N/A - use Radiqal within Medicalis/VuePACS",
        "other": "Use Radiqal Tip Sheet guidance",
        "note": "QA system support",
        "hours": "Platform dependent",
    },
}

triage_agent = Agent(
    name="Support Triage Agent",
    instructions="""
Based on the user's description and context (subspecialty, time, location),
choose one department. Reply ONLY with valid JSON matching:

{"department": "<one of: Hospital Reading Rooms, Virtual HelpDesk, WCINYP IT, Radiqal>"}
""",
    output_type=DepartmentLabel,
    handoffs=[
        hospital_rr_agent,
        virtual_helpdesk_agent,
        wcinyp_agent,
        radiqal_agent,
    ],
    model="gpt-4o",
    input_guardrails=[radiology_scope_guardrail],
)

def run_async_task(task):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(task)

def parse_hours_string(hours_string: str):
    s = hours_string.strip()
    if s == "24/7":
        return ("00:00", "23:59")
    if "," in s:
        _, time_part = s.split(",", 1)
        s = time_part.strip()
    if "–" in s:
        start_raw, end_raw = s.split("–", 1)
        clean = lambda t: t.replace(" ", "").replace("\u202F", "")
        try:
            start = datetime.strptime(clean(start_raw), "%I%p").strftime("%H:%M")
            end   = datetime.strptime(clean(end_raw),   "%I%p").strftime("%H:%M")
            return (start, end)
        except:
            return None
    return None

def load_backend_json(path="fake_backend_data.json", index=BACKEND_EXAMPLE_INDEX):
    with open(path, "r") as f:
        arr = json.load(f)
    return arr[index]

def triage_and_get_support_info(user_input: str) -> SupportResponse:
    backend = load_backend_json()
    user_meta = backend["user"]
    ts_meta   = backend["timestamp"]

    name       = user_meta["name"]
    time_str   = ts_meta["time"].split()[0]
    date_str   = ts_meta["date"]
    dow        = ts_meta["day_of_week"]
    weekend_or = ts_meta["is_weekend_or_holiday"].lower() == "yes"

    run_res = run_async_task(Runner.run(triage_agent, user_input))
    dept = run_res.final_output.department
    if not dept or dept not in SUPPORT_DIRECTORY:
        raise ValueError(f"Triage failed, invalid department: {dept!r}")

    contact = SUPPORT_DIRECTORY[dept]

    support_ok = True
    fallback = None
    if contact["hours"].strip() != "24/7":
        rng = parse_hours_string(contact["hours"])
        if rng:
            now   = datetime.strptime(time_str, "%H:%M:%S")
            start = datetime.strptime(rng[0], "%H:%M")
            end   = datetime.strptime(rng[1], "%H:%M")
            us_h  = holidays.US()
            is_hol= date_str in us_h

            if not (start <= now <= end) or dow in ("Sat","Sun") or weekend_or or is_hol:
                support_ok = False
                for alt, info in SUPPORT_DIRECTORY.items():
                    if alt == dept or info["hours"].strip() == "24/7":
                        continue
                    rng2 = parse_hours_string(info["hours"])
                    if rng2:
                        s2 = datetime.strptime(rng2[0], "%H:%M")
                        e2 = datetime.strptime(rng2[1], "%H:%M")
                        if s2 <= now <= e2:
                            fallback = alt
                            break

    # generate and coerce the draft into a string
    draft_run = run_async_task(Runner.run(email_draft_agent, f"{user_input} Please sign the email as {name}."))
    raw = draft_run.final_output
    if isinstance(raw, str):
        draft = raw
    elif hasattr(raw, "response"):
        draft = raw.response
    elif hasattr(raw, "message"):
        draft = raw.message
    else:
        draft = str(raw)

    return SupportResponse(
        department=dept,
        phone=contact["phone"],
        email=contact["email"],
        other=contact["other"],
        note=contact["note"],
        hours=contact["hours"],
        email_draft=draft,
        support_available=support_ok,
        fallback_department=fallback,
    )
