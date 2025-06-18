import asyncio
from pydantic import BaseModel
from agents import Agent, Runner, set_default_openai_key

email_draft_agent = Agent(
    name="Email Draft Generator",
    instructions="""
    Write a friendly, natural-sounding email based on the user's description. 
    Include a greeting, a clear statement of the problem, any steps they've tried, and a polite request for help. 
    End with a courteous sign-off. Avoid technical bullet headings.
    """,
    model="gpt-4o"
)

hospital_rr_agent = Agent(
    name="Hospital Reading Rooms Agent",
    instructions="""
    For issues related to imaging workstations used for CT/MRI/PACS in hospital reading environments:
    - These are clinical PACS systems used for image viewing, loading, or workstation freezing.
    - Pain points like 'freeze when loading images' or 'can't open CT/MRI studies' are in-scope.
    Provide:
    - Phone: 4-HELP (4-4357) or (212) 932-4357
    - Email: servicedesk@nyp.org, Subject: RADSUPPORTEASTCRITICAL
    - Available 24/7
    """,
    model="gpt-4o"
)

virtual_helpdesk_agent = Agent(
    name="Virtual HelpDesk Agent",
    instructions="""
    For general workstation login or certificate issues on hospital desktops (not related to PACS or clinical image loading).
    Provide Zoom helpdesk:
    - Zoom: https://nyph.zoom.us/j/9956909465
    - Available Monday–Friday, 9 AM–5 PM
    """,
    model="gpt-4o"
)

wcinyp_agent = Agent(
    name="WCINYP IT Agent",
    instructions="""
    For home or remote access issues – VPN, Outlook sync, EPIC login errors, or email not syncing remotely.
    Provide:
    - Email: wcinypit@med.cornell.edu
    - Available 7 AM–7 PM
    """,
    model="gpt-4o"
)

radiqal_agent = Agent(
    name="Radiqal Agent",
    instructions="""
    For quality assurance or discrepancy reporting tasks like identifying mislabeled image series, missing QA tools, or Radiqal within Medicalis/VuePACS.
    Provide guidance to use Radiqal via those platforms.
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
    Determine the best support route based on the user's description:
    - If it's about PACS image loading, CT/MRI viewers freezing, or radiology workstation issues, choose "Hospital Reading Rooms".
    - If it's a hospital desktop login or certificate problem (no image loading), choose "Virtual HelpDesk".
    - If it's remote access, VPN, home workstation, EPIC, Outlook, choose "WCINYP IT".
    - If it's QA/reporting errors in Medicalis/VuePACS, choose "Radiqal".
    Return:
    {"department": "Hospital Reading Rooms"} etc.
    """,
    output_type=DepartmentLabel,
    handoffs=[hospital_rr_agent, virtual_helpdesk_agent, wcinyp_agent, radiqal_agent],
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
        hours = "24/7"
    elif dept == "Virtual HelpDesk":
        phone = "Zoom session use"
        email = ""
        hours = "Monday–Friday, 9 AM–5 PM"
    elif dept == "WCINYP IT":
        phone = ""
        email = "wcinypit@med.cornell.edu"
        hours = "7 AM–7 PM"
    elif dept == "Radiqal":
        phone = ""
        email = "Use Radiqal within Medicalis or VuePACS"
        hours = "Platform availability"
    else:
        raise ValueError("Unknown department: " + dept)

    draft = run_async_task(Runner.run(email_draft_agent, user_input))
    return SupportResponse(department=dept, phone=phone, email=email,
                           email_draft=draft.final_output, link="", hours=hours)
