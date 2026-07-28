from datetime import date, time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .models import AssignmentInfo, Assignments, ClassInfo, ClassList


def build_classroom_service(credentials):
    return build("classroom", "v1", credentials=credentials)


def get_courses(classroom) -> list[dict]:
    return (
        classroom.courses()
        .list(studentId="me", courseStates=["ACTIVE"])
        .execute()
        .get("courses", [])
    )


def parse_courses(classroom) -> ClassList:
    courses = get_courses(classroom)
    class_list = []

    for course in courses:
        try:
            response = (
                classroom.courses()
                .teachers()
                .list(courseId=course["id"], pageSize=30)
                .execute()
            )
            teachers = [
                teacher.get("profile", {})
                .get("name", {})
                .get("fullName", "Unknown teacher")
                for teacher in response.get("teachers", [])
            ]
        except HttpError:
            teachers = []

        class_list.append(
            ClassInfo(
                name=course["name"],
                course_id=course["id"],
                subject=course.get("subject"),
                description=course.get("description"),
                teachers=teachers,
            )
        )

    return ClassList(classes=class_list)


def get_my_submission(classroom, course_id: str, coursework_id: str) -> dict | None:
    response = (
        classroom.courses()
        .courseWork()
        .studentSubmissions()
        .list(courseId=course_id, courseWorkId=coursework_id, userId="me")
        .execute()
    )

    submissions = response.get("studentSubmissions", [])
    return submissions[0] if submissions else None


def parse_assignments(classroom, classes: ClassList) -> Assignments:
    assignment_list = []

    for class_info in classes.classes:
        try:
            work = (
                classroom.courses()
                .courseWork()
                .list(courseId=class_info.course_id)
                .execute()
            )

            for work_item in work.get("courseWork", []):
                if work_item.get("state") != "PUBLISHED":
                    continue

                submission = get_my_submission(classroom, class_info.course_id, work_item["id"])
                submission_state = submission.get("state") if submission else None

                if submission_state == "TURNED_IN":
                    continue

                due_date = None
                due_time = None

                if "dueDate" in work_item:
                    due_date = date(
                        work_item["dueDate"]["year"],
                        work_item["dueDate"]["month"],
                        work_item["dueDate"]["day"],
                    )

                if "dueTime" in work_item:
                    due_time = time(
                        hour=work_item["dueTime"].get("hours", 0),
                        minute=work_item["dueTime"].get("minutes", 0),
                    )

                assignment_list.append(
                    AssignmentInfo(
                        title=work_item["title"],
                        description=work_item.get("description"),
                        due_date=due_date,
                        due_time=due_time,
                        estimated_minutes=work_item.get("estimatedMinutes"),
                        course_id=class_info.course_id,
                        assignment_id=work_item["id"],
                        submission_state=submission_state,
                    )
                )

        except Exception as error:
            print(f"Coursework error for {class_info.name}: {error}")

    return Assignments(assignments=assignment_list)
