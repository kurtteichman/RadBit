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

# ——— Backend example selector ———
BACKEND_EXAMPLE_INDEX = 2  # set to 0, 1 or 2 to pick a different record

# ——— OpenAI client ———
# will read OPENAI_API_KEY from the environment (or Streamlit secrets)
_client = OpenAI()

# ——— Pydantic models ———
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

# ——— Agents ———
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
Only allow clear radiology/IT support requests through.
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

# ——— Support directory ———
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

# ——— Helpers ———
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
    # drop leading "Mon–Fri,"
    if "," in s:
        _, part = s.split(",", 1)
        s = part.strip()
    if "–" in s:
        a, b = s.split("–", 1)
        clean = lambda t: t.replace(" ", "").replace(" ", "")
        try:
            return (
                datetime.strptime(clean(a), "%I%p").strftime("%H:%M"),
                datetime.strptime(clean(b), "%I%p").strftime("%H:%M"),
            )
        except:
            return None
    return None

def load_backend_json(path="fake_backend_data.json", index=BACKEND_EXAMPLE_INDEX):
    with open(path, "r") as f:
        arr = json.load(f)
    return arr[index]

# ——— Core triage + email ———
def triage_and_get_support_info(user_input: str) -> SupportResponse:
    backend = load_backend_json()
    user_meta = backend["user"]
    ts_meta = backend["timestamp"]

    name     = user_meta["name"]
    t_str    = ts_meta["time"].split()[0]
    date_str = ts_meta["date"]
    dow      = ts_meta["day_of_week"]
    weekend  = ts_meta["is_weekend_or_holiday"].lower() == "yes"

    # 1) pick department
    tri = run_async_task(Runner.run(triage_agent, user_input))
    dept = tri.final_output.department
    if dept not in SUPPORT_DIRECTORY:
        raise ValueError(f"Triage failed, invalid department: {dept!r}")
    info = SUPPORT_DIRECTORY[dept]

    # 2) check availability & find fallback
    now = datetime.strptime(t_str, "%H:%M:%S")
    support_ok = True
    fallback = None
    if info["hours"].strip() != "24/7":
        rng = parse_hours_string(info["hours"])
        if rng:
            start = datetime.strptime(rng[0], "%H:%M")
            end   = datetime.strptime(rng[1], "%H:%M")
            is_hol = date_str in holidays.US()
            if not (start <= now <= end) or dow in ("Sat","Sun") or weekend or is_hol:
                support_ok = False
                for alt, alt_info in SUPPORT_DIRECTORY.items():
                    if alt == dept or alt_info["hours"].strip() == "24/7":
                        continue
                    r2 = parse_hours_string(alt_info["hours"])
                    if r2:
                        s2 = datetime.strptime(r2[0], "%H:%M")
                        e2 = datetime.strptime(r2[1], "%H:%M")
                        if s2 <= now <= e2:
                            fallback = alt
                            break

    # 3) email draft
    draft_run = run_async_task(
        Runner.run(email_draft_agent, f"{user_input} Please sign the email as {name}.")
    )
    raw = draft_run.final_output
    email_text = raw if isinstance(raw, str) else getattr(raw, "response", str(raw))

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

# ——— FAQ generation ———
def generate_faqs(history: list[dict]) -> list[dict]:
    """
    Given a list of history entries (with keys 'input', 'department', 'contact_info', etc.),
    return up to five FAQs as a list of {"question":..., "answer":...}.
    """
    if not history:
        return []

    # take only the most recent 20 entries for prompt brevity
    sample = history[-20:]
    prompt = (
        "You are a radiology support assistant. "
        "Given this JSON array of recent support requests:\n\n"
        f"{json.dumps(sample, indent=2)}\n\n"
        "Generate up to five frequently asked questions summarizing the user issues, "
        "and provide concise answers including department name and contact details. "
        "Return valid JSON: a list of objects with 'question' and 'answer' keys."
    )

    try:
        resp = _client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Generate FAQs from recent radiology support requests."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        text = resp.choices[0].message.content.strip()
        faqs = json.loads(text)
        # ensure each item has question & answer
        return [q for q in faqs if "question" in q and "answer" in q]
    except Exception:
        return []
