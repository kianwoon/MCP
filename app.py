from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os, json, requests
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

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
