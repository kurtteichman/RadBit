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
    TResponseInputItem,
    RunContextWrapper,
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

class SimpleRunContext:
    def __init__(self):
        self.context = {}

@input_guardrail
async def radiology_scope_guardrail(
    ctx: SimpleRunContext,
    agent: Agent,
    input: str | list[TResponseInputItem],
) -> GuardrailFunctionOutput:
    out = await Runner.run(guardrail_filter_agent, input, context=ctx.context)
    return GuardrailFunctionOutput(
        output_info=out.final_output,
        tripwire_triggered=out.final_output.is_off_topic,
    )

def keyword_based_department_routing(user_input: str) -> str | None:
    text = user_input.lower()
    if any(kw in text for kw in ["mouse speed", "gaming mouse", "change mouse sensitivity"]):
        return "WCINYP IT"
    if any(kw in text for kw in ["g hub", "mouse macro", "macros on my mouse"]):
        return "Radiqal"
    if any(kw in text for kw in ["screen scaling", "display scaling", "adjust display settings", "first time logging in"]):
        return "WCINYP IT"
    return None

hospital_rr_agent = Agent(
    name="Hospital Reading Rooms Agent",
    instructions="Support for issues during image interpretation in PACS systems like viewer freezes, CT/MRI image crashes, or diagnostic disruptions.",
    model="gpt-4o",
)
virtual_helpdesk_agent = Agent(
    name="Virtual HelpDesk Agent",
    instructions="Only handle in-hospital workstation access problems (e.g., badge logins, password resets, SSO/certificates). Do NOT handle workstation software, macros, display settings, PACS viewers, or hardware config.",
    model="gpt-4o",
)
wcinyp_agent = Agent(
    name="WCINYP IT Agent",
    instructions="Handle home/remote setup issues (e.g., VPN, EPIC, Outlook, keyboard/mouse setup, display scaling, VuePACS config, hardware problems, software installs, peripheral calibration). Also covers first-time login setup.",
    model="gpt-4o",
)
radiqal_agent = Agent(
    name="Radiqal Agent",
    instructions="Handle QA workflow breakdowns, missing templates, and system-specific issues in Radiqal, Fluency, or PACS integrations involving macros or viewer behaviors.",
    model="gpt-4o",
)

triage_agent = Agent(
    name="Support Triage Agent",
    instructions="""
Given a user support issue, choose exactly one of the following departments and return only JSON: 
{"department": "Hospital Reading Rooms"}, 
{"department": "Virtual HelpDesk"}, 
{"department": "WCINYP IT"}, 
{"department": "Radiqal"}

Use this rule set:

- WCINYP IT: Issues with display scaling, gaming mouse speed, duplicate dictation, VuePACS lossy images, Stat DX not launching, hardware setup, server address corrections (Olea/TeraRecon/Dynacad), monitor config, workstation behavior, or onboarding/first-login screen layout problems.

- Radiqal: Issues involving macros in G HUB, missing or broken Fluency templates, inability to view outside studies in VuePACS, and all QA workflow/platform discrepancies or tip sheet-based platforms.

- Hospital Reading Rooms: Crashes/freezes of the PACS viewer during interpretation, sudden PACS lockups, or reading disruptions that affect diagnostic throughput.

- Virtual HelpDesk: In-hospital desktop login/certificate/access problems (badge, Duo, SSO), ONLY if no mention of hardware config or software calibration.

Return JSON exactly like {"department": "Radiqal"}.
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
        "phone": "Phone Support (24/7): 4-HELP (212-746-4357)",
        "email": (
            "• Normal Requests (24/7): nypradtickets@nyp.org"
            "\n• On-Call (5 PM–8 AM): nypradoncall@nyp.org"
            " \n(Use for high-priority, patient-care-impacting issues)"
        ),
        "other": "Zoom Support (Mon–Fri, 9 AM–5 PM): https://nyph.zoom.us/j/9956909465",
        "note": "For support with Vue PACS, Medicalis, Fluency, and Diagnostic Workstations.",
        "hours": "See Above",
    },
    "Radiqal": {
        "phone": "N/A",
        "email": "N/A - use Radiqal within Medicalis/VuePACS",
        "other": "Use Radiqal Tip Sheet guidance",
        "note": "QA system support",
        "hours": "Platform dependent",
    },
}

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
        _, part = s.split(",", 1)
        s = part.strip()
    if "–" in s:
        a, b = s.split("–", 1)
        clean = lambda t: t.replace(" ", "").replace(" ", "")
        try:
            return (
                datetime.strptime(clean(a), "%I%p").strftime("%H:%M"),
                datetime.strptime(clean(b), "%I%p").strftime("%H:%M"),
            )
        except:
            return None
    return None

def load_backend_json(path="fake_backend_data.json", index=_BACKEND_EXAMPLE_INDEX):
    with open(path, "r") as f:
        arr = json.load(f)
    return arr[index]

def triage_and_get_support_info(user_input: str) -> SupportResponse:
    dept = keyword_based_department_routing(user_input)

    if not dept:
        guardrail_out = run_async_task(radiology_scope_guardrail(
            ctx=RunContextWrapper(context={}),
            agent=triage_agent,
            input=user_input
        ))
        if guardrail_out.tripwire_triggered:
            raise ValueError("Input was rejected by scope guardrail as off-topic.")

        tri = run_async_task(Runner.run(triage_agent, user_input))
        dept = tri.final_output.department

    if dept not in SUPPORT_DIRECTORY:
        raise ValueError(f"Triage failed, got {dept!r}")

    backend = load_backend_json()
    user_meta = backend["user"]
    ts_meta   = backend["timestamp"]

    name     = user_meta["name"]
    t_str    = ts_meta["time"].split()[0]
    date_str = ts_meta["date"]
    dow      = ts_meta["day_of_week"]
    weekend  = ts_meta["is_weekend_or_holiday"].lower() == "yes"

    info = SUPPORT_DIRECTORY[dept]

    now = datetime.strptime(t_str, "%H:%M:%S")
    support_ok = True
    fallback = "Radiqal"
    if info["hours"].strip() != "24/7":
        rng = parse_hours_string(info["hours"])
        if rng:
            start = datetime.strptime(rng[0], "%H:%M")
            end   = datetime.strptime(rng[1], "%H:%M")
            is_hol = date_str in holidays.US()
            if not (start <= now <= end) or dow in ("Sat","Sun") or weekend or is_hol:
                support_ok = False

    msgs = [
        {
            "role": "system",
            "content": (
                "You are a professional assistant that writes polite, conversational support request emails."
                "Open with 'To whom it may concern,' if no recipient name is known."
                "Summarize the issue described by the user below."
                f"Close with 'Thank you' and sign as '{name}'."
                "Avoid bullet lists; write in natural prose."
            ),
        },
        {"role": "user", "content": user_input},
    ]
    resp = _client.chat.completions.create(
        model="gpt-4o",
        messages=msgs,
        temperature=0.5,
    )
    email_text = resp.choices[0].message.content.strip()

    return SupportResponse(
        department=dept,
        phone=info["phone"],
        email=info["email"],
        other=info["other"],
        note=info["note"],
        hours=info["hours"],
        email_draft=email_text,
        support_available=support_ok,
        fallback_department=fallback,
    )

def generate_faqs(history: list[dict]) -> list[dict]:
    if not history:
        return []

    inputs = [entry["input"] for entry in history][-20:]

    system_msg = {
        "role": "system",
        "content": (
            "You are an expert assistant that reads user support request descriptions "
            "and groups them by technical theme (e.g., VPN issues, login loops). "
            "For each theme, produce a JSON object with keys:"
            "- question: a short user-like question"
            "- steps: a list of clear self-help suggestions"
            "- input_example: the exact original user request most relevant to this theme"
            "Return up to five objects as a JSON array."
        ),
    }
    user_msg = {
        "role": "user",
        "content": f"Here are recent support requests: {json.dumps(inputs, indent=2)}"
    }

    try:
        llm = _client.chat.completions.create(
            model="gpt-4o",
            messages=[system_msg, user_msg],
            temperature=0.3,
        )
        content = llm.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content.removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(content)
        if isinstance(parsed, str):
            parsed = json.loads(parsed)

        results = []
        for faq in parsed:
            input_example = faq.get("input_example", "")
            dept = keyword_based_department_routing(input_example)
            if not dept:
                triage = run_async_task(Runner.run(triage_agent, input_example))
                dept = triage.final_output.department
            contact = SUPPORT_DIRECTORY.get(dept, {})
            steps = faq.get("steps", [])
            answer = "\n### Self-Help Steps\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
            answer += "\n\n### Recommended Support Contact"
            answer += f"\n**Department**: {dept}"
            if contact.get("phone"):
                answer += f"\n**Phone**: {contact['phone']}"
            if contact.get("email"):
                answer += f"\n**Email**: {contact['email']}"
            results.append({"question": faq.get("question", "FAQ"), "answer": answer})

        return results

    except Exception as e:
        return [{"question": "OpenAI API call failed", "answer": str(e)}]
