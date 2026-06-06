def generate_brief(opportunity, score, meetings):
    account = opportunity["Account"]["Name"]
    stage = opportunity["StageName"]
    amount = opportunity.get("Amount") or 0

    # Why this matters
    reasons = []

    if amount >= 500000:
        reasons.append("High-value opportunity")

    if stage in ["Security Review", "Technical Validation"]:
        reasons.append(f"Currently in {stage}")

    if meetings:
        reasons.append("Meeting scheduled today")

    if not reasons:
        reasons.append(
            f"Open opportunity in {stage} stage that needs rep attention."
        )

    why_this_matters = ". ".join(reasons)

    # Suggested action
    if stage == "Security Review":
        action = "Prepare security questionnaire responses and unblock customer review process."

    elif stage == "Technical Validation":
        action = "Prepare technical validation agenda and confirm implementation requirements."

    elif stage in ["Proposal", "Proposal/Price Quote"]:
        action = "Follow up on proposal feedback and identify procurement blockers."

    elif stage == "Negotiation/Review":
        action = "Engage decision makers and drive commercial discussions toward close."

    elif stage == "Needs Analysis":
        action = "Validate customer requirements and identify additional stakeholders."

    else:
        action = "Review opportunity status and determine next best action."

    return {
        "account": account,
        "score": score,
        "why_this_matters": why_this_matters,
        "suggested_action": action
    }