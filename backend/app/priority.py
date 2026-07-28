from datetime import date

from .models import AssignmentInfo, Assignments, Dashboard, PrioritizedAssignment, PriorityLevel


def calculate_priority(assignment: AssignmentInfo) -> PriorityLevel:
    reasons = []
    score = 0

    if assignment.due_date is None:
        score += 5
        reasons.append("No due date; treat as backlog")
    else:
        days_until_due = (assignment.due_date - date.today()).days
        if days_until_due < 0:
            score += 100
            reasons.append("Assignment is overdue")
        elif days_until_due == 0:
            score += 80
            reasons.append("Assignment is due today")
        elif days_until_due == 1:
            score += 60
            reasons.append("Due date is very close")
        elif days_until_due <= 3:
            score += 40
            reasons.append("Due date is approaching")
        elif days_until_due <= 7:
            score += 20
            reasons.append("Due date is within a week")
        else:
            score += 10
            reasons.append("Due date is more than a week away")

    if assignment.estimated_minutes and assignment.estimated_minutes >= 90:
        score += 20
        reasons.append("Long assignment")
    elif assignment.estimated_minutes and assignment.estimated_minutes >= 45:
        score += 10
        reasons.append("Medium length assignment")

    score = min(score, 100)

    if score >= 80:
        level = "high"
    elif score >= 40:
        level = "medium"
    else:
        level = "low"

    return PriorityLevel(level=level, score=score, reasons=reasons)


def sort_by_priority(assignments: Assignments) -> list[tuple[AssignmentInfo, PriorityLevel]]:
    prioritized = [
        (assignment, calculate_priority(assignment))
        for assignment in assignments.assignments
    ]
    return sorted(prioritized, key=lambda item: item[1].score, reverse=True)


def build_dashboard(assignments: Assignments) -> Dashboard:
    prioritized = sort_by_priority(assignments)
    items = [
        PrioritizedAssignment(assignment=assignment, priority=priority)
        for assignment, priority in prioritized
    ]

    overdue_work = [
        item for item in items
        if item.assignment.due_date and item.assignment.due_date < date.today()
    ]
    upcoming_assignments = [
        item for item in items
        if item.assignment.due_date and item.assignment.due_date >= date.today()
    ]
    unscheduled_assignments = [
        item for item in items
        if item.assignment.due_date is None
    ]

    return Dashboard(
        to_do=items[:5],
        upcoming_assignments=upcoming_assignments,
        overdue_assignments=overdue_work,
        unscheduled_assignments=unscheduled_assignments,
    )
