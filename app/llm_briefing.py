from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)


def generate_llm_meeting_brief(opportunity, meetings):
    account = opportunity["Account"]["Name"]
    stage = opportunity["StageName"]
    amount = opportunity.get("Amount") or 0
    close_date = opportunity.get("CloseDate")
    meeting_names = [m["Subject"] for m in meetings]

    prompt = f"""
You are an AI sales copilot helping a GTM rep prepare for their day.

Generate a concise meeting brief using the CRM context below.

Account: {account}
Opportunity: {opportunity["Name"]}
Stage: {stage}
Amount: ${amount:,.0f}
Close Date: {close_date}
Meetings Today: {meeting_names}

Return the brief in this format:

Account Summary:
Deal Status:
Key Risks:
Suggested Talking Points:
Next Best Action:
"""

    response = llm.invoke(prompt)
    return response.content