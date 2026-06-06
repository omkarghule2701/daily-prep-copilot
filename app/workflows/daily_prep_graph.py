from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

from simple_salesforce import Salesforce
from dotenv import load_dotenv
import os

from app.prioritization import calculate_priority
from app.briefing import generate_brief
from app.llm_briefing import generate_llm_meeting_brief

load_dotenv()


class DailyPrepState(TypedDict):
    opportunities: List[Dict[str, Any]]
    tasks: List[Dict[str, Any]]
    tasks_by_account_id: Dict[str, List[Dict[str, Any]]]
    ranked_opportunities: List[Dict[str, Any]]
    digest: str


def fetch_salesforce_context(state: DailyPrepState):
    sf = Salesforce(
        username=os.getenv("SF_USERNAME"),
        password=os.getenv("SF_PASSWORD"),
        security_token=os.getenv("SF_SECURITY_TOKEN")
    )

    opportunity_query = """
    SELECT
        Id,
        Name,
        StageName,
        Amount,
        CloseDate,
        Account.Id,
        Account.Name,
        Account.Industry,
        Account.NumberOfEmployees
    FROM Opportunity
    WHERE IsClosed = false
    ORDER BY Amount DESC
    """

    task_query = """
    SELECT
        Id,
        Subject,
        ActivityDate,
        Status,
        Priority,
        Description,
        AccountId,
        Account.Name
    FROM Task
    WHERE ActivityDate = TODAY
    ORDER BY Priority DESC
    """

    opportunities = sf.query_all(opportunity_query)["records"]
    tasks = sf.query_all(task_query)["records"]

    return {
        **state,
        "opportunities": opportunities,
        "tasks": tasks
    }


def group_tasks_by_account(state: DailyPrepState):
    tasks_by_account_id = {}

    for task in state["tasks"]:
        account_id = task.get("AccountId")
        if account_id:
            tasks_by_account_id.setdefault(account_id, []).append(task)

    return {
        **state,
        "tasks_by_account_id": tasks_by_account_id
    }


def prioritize_opportunities(state: DailyPrepState):
    tasks_by_account_id = state["tasks_by_account_id"]

    ranked = sorted(
        state["opportunities"],
        key=lambda opp: calculate_priority(opp, tasks_by_account_id),
        reverse=True
    )

    return {
        **state,
        "ranked_opportunities": ranked
    }


def build_daily_digest(state: DailyPrepState):
    lines = []
    lines.append("# 🚀 Daily Prep Digest")
    lines.append("")

    for i, opp in enumerate(state["ranked_opportunities"][:5], start=1):
        account = opp["Account"]["Name"]
        account_id = opp["Account"]["Id"]

        meetings = state["tasks_by_account_id"].get(account_id, [])
        score = calculate_priority(opp, state["tasks_by_account_id"])

        brief = generate_brief(opp, score, meetings)

        lines.append(f"## {i}. {account}")
        lines.append("")
        lines.append(f"**Opportunity:** {opp['Name']}")
        lines.append(f"**Stage:** {opp['StageName']}")
        lines.append(f"**Amount:** ${(opp.get('Amount') or 0):,.0f}")
        lines.append(f"**Priority Score:** {score}")
        lines.append("")
        lines.append(f"**Why This Matters:** {brief['why_this_matters']}")
        lines.append("")
        lines.append(f"**Suggested Action:** {brief['suggested_action']}")
        lines.append("")

        if meetings:
            lines.append("**Meetings Today:**")
            for meeting in meetings:
                lines.append(f"- {meeting['Subject']}")
            lines.append("")

        if i == 1:
            lines.append("### AI Meeting Brief")
            lines.append("")
            lines.append(generate_llm_meeting_brief(opp, meetings))
            lines.append("")

    digest = "\n".join(lines)

    with open("daily_digest.md", "w") as f:
        f.write(digest)

    return {
        **state,
        "digest": digest
    }


def build_graph():
    graph = StateGraph(DailyPrepState)

    graph.add_node("fetch_salesforce_context", fetch_salesforce_context)
    graph.add_node("group_tasks_by_account", group_tasks_by_account)
    graph.add_node("prioritize_opportunities", prioritize_opportunities)
    graph.add_node("build_daily_digest", build_daily_digest)

    graph.set_entry_point("fetch_salesforce_context")

    graph.add_edge("fetch_salesforce_context", "group_tasks_by_account")
    graph.add_edge("group_tasks_by_account", "prioritize_opportunities")
    graph.add_edge("prioritize_opportunities", "build_daily_digest")
    graph.add_edge("build_daily_digest", END)

    return graph.compile()


if __name__ == "__main__":
    app = build_graph()

    png_data = app.get_graph().draw_mermaid_png()

    with open("langgraph.png", "wb") as f:
        f.write(png_data)

    print("Saved langgraph.png")

    initial_state = {
        "opportunities": [],
        "tasks": [],
        "tasks_by_account_id": {},
        "ranked_opportunities": [],
        "digest": ""
    }

    final_state = app.invoke(initial_state)

    print(final_state["digest"])
    print("\nSaved digest to daily_digest.md")