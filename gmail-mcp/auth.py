"""Run this once locally to generate token.json."""
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
DIR = os.path.dirname(os.path.abspath(__file__))

flow = InstalledAppFlow.from_client_secrets_file(
    os.path.join(DIR, "credentials.json"), SCOPES
)
creds = flow.run_local_server(port=0)

token_path = os.path.join(DIR, "token.json")
with open(token_path, "w") as f:
    f.write(creds.to_json())

print(f"Done — token saved to {token_path}")
