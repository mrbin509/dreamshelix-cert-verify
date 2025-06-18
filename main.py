from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

app = FastAPI()

# Mount static and template directories
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Load Google credentials from ENV (secure for Railway)
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
google_creds_dict = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds_dict, scope)
client = gspread.authorize(creds)

# Open your certificate sheet
SHEET_NAME = "student_details"  # <-- Replace with your Google Sheet name
sheet = client.open(SHEET_NAME).sheet1   # or .worksheet("Sheet1") if named

@app.get("/", response_class=HTMLResponse)
async def verify_form(request: Request):
    return templates.TemplateResponse("verify.html", {"request": request, "message": "", "status": ""})

@app.post("/verify", response_class=HTMLResponse)
async def verify_certificate(request: Request, cert_id: str = Form(...)):
    data = sheet.get_all_records()

    result = next((row for row in data if str(row.get("CertificateID")).strip() == cert_id.strip()), None)

    if result:
        name = result.get("Name")
        course = result.get("Course")
        issue_date = result.get("IssueDate")
        status = result.get("Status")
        pdf_link = result.get("PDFLink", "#")

        message = f"""
        ✅ <strong>Certificate Verified</strong><br><br>
        <strong>Name:</strong> {name}<br>
        <strong>Course:</strong> {course}<br>
        <strong>Issued On:</strong> {issue_date}<br>
        <strong>Status:</strong> {status}<br><br>
        <a href="{pdf_link}" target="_blank">🔗 Download Certificate PDF</a>
        """
        return templates.TemplateResponse("verify.html", {
            "request": request,
            "message": message,
            "status": "success"
        })
    else:
        return templates.TemplateResponse("verify.html", {
            "request": request,
            "message": "❌ No certificate found with this ID. Please check again.",
            "status": "error"
        })