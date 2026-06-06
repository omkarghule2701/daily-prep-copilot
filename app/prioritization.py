def calculate_priority(opp, tasks_by_account_id):
    score = 0

    amount = opp.get("Amount") or 0
    stage = opp.get("StageName") or ""

    # Deal size score
    if amount >= 1_000_000:
        score += 40
    elif amount >= 500_000:
        score += 30
    elif amount >= 250_000:
        score += 20
    else:
        score += 10

    # Stage score
    stage_scores = {
        "Security Review": 30,
        "Procurement": 30,
        "Negotiation/Review": 30,
        "Proposal": 20,
        "Proposal/Price Quote": 20,
        "Technical Validation": 20,
        "Needs Analysis": 15,
        "Value Proposition": 15,
        "Id. Decision Makers": 10,
        "Qualification": 10,
        "Prospecting": 5,
    }

    score += stage_scores.get(stage, 0)

    # Meeting today score
    account_id = opp["Account"]["Id"]
    if tasks_by_account_id.get(account_id):
        score += 20

    return score