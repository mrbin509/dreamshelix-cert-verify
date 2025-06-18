# app.py

import os
import csv
import json
import datetime
import qrcode
from PIL import Image, ImageDraw, ImageFont

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# -------------------- CONFIG --------------------
SHEET_NAME = "student_details"
CERT_TEMPLATE_PATH = "certificate_template.png"
CERTIFICATES_DIR = "certificates"
FONT_PATH = "arial.ttf"  # Make sure this font is present
FONT_SIZE = 50
QR_SIZE = 150

# FastAPI setup
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Ensure cert dir exists
os.makedirs(CERTIFICATES_DIR, exist_ok=True)

# -------------------- GOOGLE SHEET & DRIVE SETUP --------------------

def get_google_credentials():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    if os.getenv('GOOGLE_CREDENTIALS_JSON'):
        creds_json = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return creds

creds = get_google_credentials()
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# PyDrive auth (only used for uploading in certificate generation, skip for FastAPI requests)
def get_drive():
    gauth = GoogleAuth()
    gauth.LocalWebserverAuth()
    return GoogleDrive(gauth)

# -------------------- CERTIFICATE GENERATION --------------------

def generate_certificate(cert_id, name, course):
    cert = Image.open(CERT_TEMPLATE_PATH).convert("RGB")
    draw = ImageDraw.Draw(cert)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    draw.text((450, 400), name, font=font, fill="black")
    draw.text((450, 500), course, font=font, fill="black")
    draw.text((450, 600), datetime.date.today().strftime("%B %d, %Y"), font=font, fill="black")

    qr = qrcode.make(cert_id)
    qr = qr.resize((QR_SIZE, QR_SIZE))
    cert.paste(qr, (1000, 600))

    pdf_path = f"{CERTIFICATES_DIR}/{cert_id}.pdf"
    cert.save(pdf_path, "PDF")
    return pdf_path

def upload_to_drive(pdf_path, cert_id):
    drive = get_drive()
    file = drive.CreateFile({'title': f'{cert_id}.pdf'})
    file.SetContentFile(pdf_path)
    file.Upload()
    file.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
    return file['alternateLink']

# -------------------- BULK GENERATION --------------------

def generate_all_certificates():
    with open("students.csv", "r") as f:
        reader = csv.DictReader(f)
        for index, row in enumerate(reader, start=1):
            name = row["Name"]
            course = row["Course"]
            cert_id = f"1PYTH{str(index).zfill(3)}"
            print(f"Generating certificate for {name} - ID: {cert_id}")

            pdf_path = generate_certificate(cert_id, name, course)
            pdf_link = upload_to_drive(pdf_path, cert_id)

            sheet.append_row([
                cert_id,
                name,
                course,
                datetime.date.today().isoformat(),
                "Verified",
                pdf_link
            ])

# -------------------- FASTAPI VERIFY ROUTES --------------------

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

# -------------------- OPTIONAL: Run generation locally --------------------
if __name__ == "__main__":
    generate_all_certificates()