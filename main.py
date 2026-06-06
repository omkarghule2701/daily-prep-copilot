from simple_salesforce import Salesforce
from dotenv import load_dotenv
from app.prioritization import calculate_priority
import os
from app.briefing import generate_brief
from app.llm_briefing import generate_llm_meeting_brief

load_dotenv()

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

opportunity_result = sf.query_all(opportunity_query)
task_result = sf.query_all(task_query)

opportunities = opportunity_result["records"]
tasks = task_result["records"]

tasks_by_account_id = {}

for task in tasks:
    account_id = task.get("AccountId")
    if account_id:
        tasks_by_account_id.setdefault(account_id, []).append(task)

ranked_opportunities = sorted(
    opportunities,
    key=lambda opp: calculate_priority(opp, tasks_by_account_id),
    reverse=True
)

print("\n🚀 Daily Prep Digest\n")

for i, opp in enumerate(ranked_opportunities[:5], start=1):

    account = opp["Account"]["Name"]
    account_id = opp["Account"]["Id"]

    score = calculate_priority(
        opp,
        tasks_by_account_id
    )

    meetings = tasks_by_account_id.get(
        account_id,
        []
    )

    brief = generate_brief(
        opp,
        score,
        meetings
    )

    print(f"{i}. {brief['account']}")
    print(f"   Priority Score: {brief['score']}")
    print(f"   Why This Matters: {brief['why_this_matters']}")
    print(f"   Suggested Action: {brief['suggested_action']}")

    if meetings:
        print("   Meetings Today:")
        for meeting in meetings:
            print(f"   - {meeting['Subject']}")

    if i == 1:
        print("   AI Meeting Brief:")
        brief_text = generate_llm_meeting_brief(opp, meetings)
        print(brief_text)

    print()