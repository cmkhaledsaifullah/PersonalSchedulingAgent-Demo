"""
Google OAuth2 authentication module.

Handles the OAuth2 flow for Gmail and Google Calendar APIs.
Tokens are cached locally in token.pickle so the user only
authenticates once.

Required Google Cloud scopes:
  - https://www.googleapis.com/auth/gmail.readonly
  - https://www.googleapis.com/auth/calendar
"""

import os
import pickle
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Gmail (read-only) + Calendar (full access for creating events)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
]

# Paths relative to the project root
PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / "token.pickle"


def get_google_credentials(
    credentials_file: Optional[Path] = None,
    token_file: Optional[Path] = None,
) -> Credentials:
    """
    Return valid Google OAuth2 credentials.

    On first run this opens a browser window for the OAuth consent flow.
    On subsequent runs the cached token is refreshed automatically.

    Args:
        credentials_file: Path to the OAuth2 client secrets JSON downloaded
                          from Google Cloud Console. Defaults to
                          ``credentials.json`` in the project root.
        token_file:       Path to persist the OAuth2 token. Defaults to
                          ``token.pickle`` in the project root.

    Returns:
        google.oauth2.credentials.Credentials ready for use with
        googleapiclient.discovery.build().

    Raises:
        FileNotFoundError: If credentials_file does not exist.
    """
    creds_path = credentials_file or CREDENTIALS_FILE
    tok_path = token_file or TOKEN_FILE

    if not creds_path.exists():
        raise FileNotFoundError(
            f"OAuth2 credentials file not found: {creds_path}\n"
            "Download it from Google Cloud Console → APIs & Services → "
            "Credentials and save it as 'credentials.json' in the project root."
        )

    creds: Optional[Credentials] = None

    # Load cached token if it exists
    if tok_path.exists():
        with open(tok_path, "rb") as f:
            creds = pickle.load(f)

    # Refresh or re-authenticate as needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

        # Persist the token for next run
        with open(tok_path, "wb") as f:
            pickle.dump(creds, f)

    return creds
