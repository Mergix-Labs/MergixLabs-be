from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secret.json",
    scopes=SCOPES
)

creds = flow.run_local_server(
    port=8080,
    access_type="offline",
    prompt="consent"
)

print("=" * 50)
print("ACCESS TOKEN:")
print(creds.token)
print("=" * 50)
print("REFRESH TOKEN:")
print(creds.refresh_token)
print("=" * 50)