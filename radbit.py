import asyncio
from pydantic import BaseModel
from agents import Agent, Runner, set_default_openai_key

hospital_rr_agent = Agent(
    name="Hospital Reading Rooms Agent",
    instructions="""
    You are the support agent for Hospital Reading Rooms at Cornell, LMH, and BMH.
    Handle urgent clinical or workstation support for radiologists on-site at those hospitals.
    Contact options:
    Phone: 4-HELP (4-4357) or (212) 932-4357
    Email: servicedesk@nyp.org with Subject: RADSUPPORTEASTCRITICAL
    Availability: 24 hours
    Provide instructions on how to contact and create a clean summary email.
    """,
    model="gpt-4o"
)

virtual_helpdesk_agent = Agent(
    name="Virtual HelpDesk Agent",
    instructions="""
    You are the NYP Virtual HelpDesk agent for Cornell, LMH, and BMH.
    Handle Zoom-based support requests for general issues Monday through Friday, 9am–5pm.
    Zoom: https://nyph.zoom.us/j/9956909465
    Provide connection instructions and generate a clean support email summary if necessary.
    """,
    model="gpt-4o"
)

wcinyp_agent = Agent(
    name="WCINYP IT Agent",
    instructions="""
    You are WCINYP IT Support. Handle issues related to email access, VPN, hospital system access, and general teleradiology IT for WCINYP sites and home setups.
    Email: wcinypit@med.cornell.edu
    Availability: 7am–7pm
    Generate a clean support summary and list appropriate actions.
    """,
    model="gpt-4o"
)

radiqal_agent = Agent(
    name="Radiqal Agent",
    instructions="""
    You are the Radiqal support agent. Guide radiologists to submit QA or ticketing issues using Radiqal via Medicalis or VuePACS.
    Provide guidance based on the Radiqal Tip Sheet if needed.
    Summarize the user query into a brief QA ticket description if appropriate.
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
    Route the user query to one of the following support groups: 
    - Hospital Reading Rooms
    - Virtual HelpDesk
    - WCINYP IT
    - Radiqal

    Choose the best one based on the query and return:
    {"department": "Hospital Reading Rooms"}, etc.
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
        agent = hospital_rr_agent
        phone = "4-HELP (4-4357) or (212) 932-4357"
        email = "servicedesk@nyp.org"
        hours = "24 hours"
        link = "Subject line: RADSUPPORTEASTCRITICAL"
    elif dept == "Virtual HelpDesk":
        agent = virtual_helpdesk_agent
        phone = "Zoom only"
        email = "N/A"
        hours = "Monday–Friday, 9 AM to 5 PM"
        link = "https://nyph.zoom.us/j/9956909465"
    elif dept == "WCINYP IT":
        agent = wcinyp_agent
        phone = "N/A"
        email = "wcinypit@med.cornell.edu"
        hours = "7 AM to 7 PM"
        link = ""
    elif dept == "Radiqal":
        agent = radiqal_agent
        phone = "N/A"
        email = "Use Medicalis or VuePACS"
        hours = "Based on platform availability"
        link = "Radiqal Tip Sheet"
    else:
        raise ValueError("Unknown department returned by triage agent.")

    support_response = run_async_task(Runner.run(agent, user_input))

    return SupportResponse(
        department=dept,
        phone=phone,
        email=email,
        email_draft=support_response.final_output,
        link=link,
        hours=hours
    )
