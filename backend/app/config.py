from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = ZoneInfo("America/Chicago")
DEFAULT_USER_ID = "me"
DATABASE_PATH = ".catchup/catchup.sqlite3"

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]
