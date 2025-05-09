from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, json, requests
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# --- CORS Configuration ---
# Read allowed origins from environment variable, defaulting to an empty list if not set
allowed_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "")
origins = [origin.strip() for origin in allowed_origins_str.split(',') if origin.strip()]

# If no origins are specified in the environment variable, you might want to add a default
# or handle it as an error, depending on your security requirements.
# For now, it will use what's in CORS_ALLOWED_ORIGINS. If empty, no origins will be allowed.
# Example of adding a default if none are provided:
# if not origins:
#     origins = [
#         "http://localhost:5173", # Default frontend origin for development
#         "http://127.0.0.1:5173",
#     ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # Use the dynamically loaded list of origins
    allow_credentials=True,      # Allow cookies if needed
    allow_methods=["*"],         # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],         # Allow all headers
)
# --- End CORS Configuration ---

# Load MCP manifest
def load_manifest():
    with open("manifest.json") as f:
        return json.load(f)
manifest = load_manifest()

@app.get("/manifest")
def get_manifest():
    return manifest

class Invocation(BaseModel):
    name: str
    arguments: dict

@app.post("/invoke")
def invoke(inv: Invocation):
    name, args = inv.name, inv.arguments
    try:
        if name == "jira_list_issues":
            url = os.getenv("JIRA_URL") + "/rest/api/2/search"
            auth = (os.getenv("JIRA_USER"), os.getenv("JIRA_TOKEN"))
            resp = requests.get(url, params={"jql": args["jql"]}, auth=auth)
            return {"result": resp.json()}

        if name == "jira_create_issue":
            url = os.getenv("JIRA_URL") + "/rest/api/2/issue"
            auth = (os.getenv("JIRA_USER"), os.getenv("JIRA_TOKEN"))
            payload = {"fields": {
                "project": {"key": args["project_key"]},
                "summary": args["summary"],
                "description": args.get("description", ""),
                "issuetype": {"name": args["issue_type"]}
            }}
            resp = requests.post(url, json=payload, auth=auth)
            return {"result": resp.json()}

        if name in ("outlook_list_events","outlook_create_event","outlook_list_messages","outlook_send_message"):
            # Simplified Graph API wrapper
            graph_url = "https://graph.microsoft.com/v1.0/me"
            token = os.getenv("MS_GRAPH_TOKEN")
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            if name == "outlook_list_events":
                url = f"{graph_url}/calendarview?startDateTime={args['start_datetime']}&endDateTime={args['end_datetime']}"
                data = requests.get(url, headers=headers).json()
            elif name == "outlook_create_event":
                url = f"{graph_url}/events"
                body = {"subject": args["subject"], "start": {"dateTime": args["start_datetime"],"timeZone": "UTC"},
                        "end": {"dateTime": args["end_datetime"],"timeZone": "UTC"},
                        "attendees": [{"emailAddress": {"address": e},"type": "required"} for e in args.get("attendees", [])]}
                data = requests.post(url, headers=headers, json=body).json()
            elif name == "outlook_list_messages":
                url = f"{graph_url}/mailFolders/{args['folder']}/messages?$top={args.get('top',5)}"
                data = requests.get(url, headers=headers).json()
            else: # outlook_send_message
                url = f"{graph_url}/sendMail"
                mail = {"message": {"subject": args['subject'],"body": {"contentType": "Text","content": args['body']},"toRecipients": [{"emailAddress": {"address": r}} for r in args['to']]}}
                data = requests.post(url, headers=headers, json=mail).status_code
            return {"result": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    raise HTTPException(status_code=400, detail=f"Unknown tool '{name}'")
