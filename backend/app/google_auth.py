import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .config import GOOGLE_SCOPES


os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"


def find_file(*candidates: str) -> Path:
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    raise FileNotFoundError(f"Could not find any of: {', '.join(candidates)}")


def get_google_credentials(
    credentials_path: Path | None = None,
    token_path: Path | None = None,
) -> Credentials:
    credentials_path = credentials_path or find_file("credentials.json", "testing/credentials.json")
    token_path = token_path or credentials_path.parent / "token.json"

    credentials = None

    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path), GOOGLE_SCOPES)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), GOOGLE_SCOPES)
            credentials = flow.run_local_server(port=0)

        token_path.write_text(credentials.to_json(), encoding="utf-8")

    return credentials
