import asyncio
from pydantic import BaseModel
from agents import Agent, Runner, set_default_openai_key

radsupport_agent = Agent(
    name="Radsupport Agent",
    instructions="""
    You are Radsupport. Handle issues related to PACS systems, radiology workflow tools, imaging software, and radiologist workstation problems. 
    If a user's query involves clinical imaging tools, viewer errors, radiologist login, or interpretation-related tech, respond with the Radsupport contact:
    Phone: (212) 746-2323
    Email: radsupport@med.cornell.edu
    Also, compile a clean email draft summarizing the user input which you would send to Radsupport (yourself) to get additional help.
    """,
    model="gpt-4o"
)

wcit_agent = Agent(
    name="WCINYP IT Agent",
    instructions="""
    You are WCINYP IT Support. Handle issues related to email access, password resets, internet connectivity, hospital system access, VPN problems, and general IT services.
    If a user's query involves computer access, login issues unrelated to imaging tools, or software installation, respond with the WCINYP IT contact:
    Phone: (212) 746-4878
    Email: support@med.cornell.edu
    Also, compile a clean email draft summarizing the user input which you would send to WCINYP (yourself) to get additional help.
    """,
    model="gpt-4o"
)

class SupportResponse(BaseModel):
    department: str  # "Radsupport" or "WCINYP IT"
    phone: str
    email: str
    email_draft: str

triage_agent = Agent(
    name="Support Triage Agent",
    instructions="""
    Route the user query to the correct support group: Radsupport or WCINYP IT.
    Only choose one based on the query content. Return your response in JSON format:
    {"department": "Radsupport"} or {"department": "WCINYP IT"}
    """,
    output_type=BaseModel.construct(__annotations__={"department": str}),
    handoffs=[radsupport_agent, wcit_agent],
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

    if dept.lower() == "radsupport":
        agent = radsupport_agent
    elif dept.lower() == "wcinyp it":
        agent = wcit_agent
    else:
        raise ValueError("Unknown department returned by triage agent.")

    support_response = run_async_task(Runner.run(agent, user_input))

    return SupportResponse(
        department=dept,
        phone="(212) 746-2323" if dept == "Radsupport" else "(212) 746-4878",
        email="radsupport@med.cornell.edu" if dept == "Radsupport" else "support@med.cornell.edu",
        email_draft=support_response.final_output
    )
