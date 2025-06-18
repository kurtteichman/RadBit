import asyncio
from pydantic import BaseModel
from agents import Agent, Runner, set_default_openai_key

email_draft_agent = Agent(
    name="Email Draft Generator",
    instructions="""
    You are a helpful assistant that converts a user's issue into a professional but human-sounding email to IT or clinical support.
    The email should have a greeting, clearly describe the issue in natural language, and include any relevant actions the user has already taken.
    Avoid bullet points, headings, or formatting like "Impact:" or "Issue:". End with a polite request for help and a sign-off.
    """,
    model="gpt-4o"
)

hospital_rr_agent = Agent(
    name="Hospital Reading Rooms Agent",
    instructions="""
    Handle urgent clinical workstation and PACS issues at Cornell, LMH, and BMH.
    Contact info:
    - Phone: 4-HELP (4-4357) or (212) 932-4357
    - Email: servicedesk@nyp.org with Subject: RADSUPPORTEASTCRITICAL
    - Hours: 24/7
    """,
    model="gpt-4o"
)

virtual_helpdesk_agent = Agent(
    name="Virtual HelpDesk Agent",
    instructions="""
    Handle Zoom-based support for general IT issues at Cornell, LMH, and BMH.
    Zoom: https://nyph.zoom.us/j/9956909465
    Hours: Monday–Friday, 9am–5pm
    """,
    model="gpt-4o"
)

wcinyp_agent = Agent(
    name="WCINYP IT Agent",
    instructions="""
    Handle WCINYP teleradiology and home workstation issues: VPN, Outlook, login, etc.
    Email: wcinypit@med.cornell.edu
    Hours: 7am–7pm
    """,
    model="gpt-4o"
)

radiqal_agent = Agent(
    name="Radiqal Agent",
    instructions="""
    Guide users to submit QA or discrepancy tickets using Radiqal via Medicalis or VuePACS.
    Hours: Based on platform availability.
    """,
    model="gpt-4o"
)

class SupportResponse(BaseModel):
    department: str
    phone: str
    email: str
    email_draft: str
    link: str = ""
    hours: str = ""

class DepartmentLabel(BaseModel):
    department: str

triage_agent = Agent(
    name="Support Triage Agent",
    instructions="""
    Route the user query to one of the following:
    - Hospital Reading Rooms
    - Virtual HelpDesk
    - WCINYP IT
    - Radiqal

    Only select one. Respond using:
    {"department": "Hospital Reading Rooms"} or similar.
    """,
    output_type=DepartmentLabel,
    handoffs=[
        hospital_rr_agent,
        virtual_helpdesk_agent,
        wcinyp_agent,
        radiqal_agent
    ],
    model="gpt-4o"
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

    if dept == "Hospital Reading Rooms":
        phone = "4-HELP (4-4357) or (212) 932-4357"
        email = "servicedesk@nyp.org (Subject: RADSUPPORTEASTCRITICAL)"
        hours = "24 hours"
        link = ""
        agent = hospital_rr_agent
    elif dept == "Virtual HelpDesk":
        phone = "Zoom: https://nyph.zoom.us/j/9956909465"
        email = "N/A"
        hours = "Monday–Friday, 9 AM to 5 PM"
        link = ""
        agent = virtual_helpdesk_agent
    elif dept == "WCINYP IT":
        phone = "N/A"
        email = "wcinypit@med.cornell.edu"
        hours = "7 AM to 7 PM"
        link = ""
        agent = wcinyp_agent
    elif dept == "Radiqal":
        phone = "N/A"
        email = "Use Medicalis or VuePACS"
        hours = "Dependent on platform availability"
        link = "Radiqal Tip Sheet"
        agent = radiqal_agent
    else:
        raise ValueError("Unknown department returned by triage agent.")

    run_async_task(Runner.run(agent, user_input)) 

    draft_result = run_async_task(Runner.run(email_draft_agent, user_input))

    return SupportResponse(
        department=dept,
        phone=phone,
        email=email,
        email_draft=draft_result.final_output,
        link=link,
        hours=hours
    )
