"""ScholarPath major-project decision layer.

Builds on the existing eligibility matching engine and answers:
- Which eligible scholarships should the student prioritize?
- How ready is the student to apply?
- What should the student do next?
"""
from datetime import date, datetime


def _deadline_days(deadline):
    if not deadline:
        return None
    try:
        return (datetime.strptime(deadline, "%Y-%m-%d").date() - date.today()).days
    except (ValueError, TypeError):
        return None


def _criteria_score(explanation):
    leaves = []

    def walk(node):
        if not isinstance(node, dict):
            return
        t = node.get("type")
        if t == "leaf":
            leaves.append(node)
        elif t in ("and", "or"):
            for child in node.get("children", []):
                walk(child)
        elif t == "not":
            walk(node.get("child", {}))

    walk(explanation)
    if not leaves:
        return 100, 0, 0
    passed = sum(bool(x.get("passed")) for x in leaves)
    return round(passed / len(leaves) * 100), passed, len(leaves)


def _deadline_score(days):
    if days is None:
        return 45
    if days < 0:
        return 0
    if days <= 7:
        return 100
    if days <= 14:
        return 90
    if days <= 30:
        return 75
    if days <= 60:
        return 55
    return 35


def _funding_score(amount, max_amount):
    if not amount or not max_amount:
        return 40
    return round((amount / max_amount) * 100)


def application_readiness(scholarship, student_documents):
    required = [x.strip() for x in (scholarship.required_documents or "").split(",") if x.strip()]
    if not required:
        return {
            "required": [], "available": [], "missing": [],
            "percent": 100, "ready": True
        }
    available = {d.document_type.strip().lower() for d in student_documents if d.file_path}
    available_required = [x for x in required if x.lower() in available]
    missing = [x for x in required if x.lower() not in available]
    percent = round(len(available_required) / len(required) * 100)
    return {
        "required": required,
        "available": available_required,
        "missing": missing,
        "percent": percent,
        "ready": not missing,
    }


def priority_score(scholarship, explanation, readiness):
    criteria, _, _ = _criteria_score(explanation)
    days = _deadline_days(scholarship.deadline)
    deadline = _deadline_score(days)
    # Funding is normalized by the largest eligible award before scoring.
    return criteria, deadline, readiness["percent"], days


def rank_matches(matches, student_documents):
    if not matches:
        return []
    max_amount = max((s.amount or 0) for s, _ in matches) or 1
    ranked = []
    for scholarship, explanation in matches:
        readiness = application_readiness(scholarship, student_documents)
        criteria, passed, total = _criteria_score(explanation)
        days = _deadline_days(scholarship.deadline)
        deadline = _deadline_score(days)
        funding = _funding_score(scholarship.amount or 0, max_amount)
        # Eligibility remains dominant; the new layer adds practical decision factors.
        score = round(criteria * 0.50 + funding * 0.20 + deadline * 0.15 + readiness["percent"] * 0.15)
        if days is not None and days < 0:
            score = min(score, 20)
        ranked.append({
            "scholarship": scholarship,
            "explanation": explanation,
            "score": score,
            "criteria_score": criteria,
            "criteria_passed": passed,
            "criteria_total": total,
            "deadline_score": deadline,
            "funding_score": funding,
            "deadline_days": days,
            "readiness": readiness,
        })
    return sorted(ranked, key=lambda x: (-x["score"], x["deadline_days"] if x["deadline_days"] is not None else 999999, -(x["scholarship"].amount or 0)))


def next_actions(item, application=None):
    actions = []
    readiness = item["readiness"]
    if readiness["missing"]:
        for doc in readiness["missing"][:3]:
            actions.append({"title": f"Get {doc}", "kind": "document", "urgent": item["deadline_days"] is not None and item["deadline_days"] <= 14})
    if not application:
        actions.append({"title": "Review and start application", "kind": "apply", "urgent": item["deadline_days"] is not None and item["deadline_days"] <= 14})
    elif application.status == "Applied":
        actions.append({"title": "Monitor application status", "kind": "status", "urgent": False})
    elif application.status == "Under Review":
        actions.append({"title": "Wait for provider review", "kind": "status", "urgent": False})
    return actions[:4]
