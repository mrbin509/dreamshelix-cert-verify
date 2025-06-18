import csv
import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
import datetime
import json

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# -------------------- CONFIG --------------------
SHEET_NAME = "student_details"
CERT_TEMPLATE_PATH = "certificate.jpg"
CERTIFICATES_DIR = "certificates"
QRCODE_DIR = "qrcodes"
FONT_PATH = "GreatVibes-Regular.ttf"  # Change to your font path
FONT_SIZE = 50
QR_SIZE = 150

# Create cert dir if missing
os.makedirs(CERTIFICATES_DIR, exist_ok=True)
os.makedirs(QRCODE_DIR, exist_ok=True)

# -------------------- GOOGLE SETUP --------------------
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

gauth = GoogleAuth()
gauth.LocalWebserverAuth()
drive = GoogleDrive(gauth)

# -------------------- HELPER FUNCTION --------------------
def generate_certificate(cert_id, name, course):
    # Load and draw on certificate
    cert = Image.open(CERT_TEMPLATE_PATH).convert("RGB")
    draw = ImageDraw.Draw(cert)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    # Draw text
    draw.text((450, 400), name, font=font, fill="black")
    draw.text((450, 500), course, font=font, fill="black")
    draw.text((450, 600), datetime.date.today().strftime("%B %d, %Y"), font=font, fill="black")

    # Generate QR code
    qr = qrcode.make(cert_id)
    qr = qr.resize((QR_SIZE, QR_SIZE))
    cert.paste(qr, (1000, 600))  # Adjust (x,y) for QR position

    # Save to PDF
    pdf_path = f"{CERTIFICATES_DIR}/{cert_id}.pdf"
    cert.save(pdf_path, "PDF")
    return pdf_path

def upload_to_drive(pdf_path, cert_id):
    file = drive.CreateFile({'title': f'{cert_id}.pdf'})
    file.SetContentFile(pdf_path)
    file.Upload()
    file['sharingUser'] = {'role': 'reader', 'type': 'anyone'}
    file.Upload()
    return file['alternateLink']

# -------------------- MAIN --------------------
def main():
    with open("students.csv", "r") as f:
        reader = csv.DictReader(f)
        for index, row in enumerate(reader, start=1):
            name = row["Name"]
            course = row["Course"]
            cert_id = f"1PYTH{str(index).zfill(3)}"
            print(f"Generating certificate for {name} - ID: {cert_id}")

            # Generate cert
            pdf_path = generate_certificate(cert_id, name, course)

            # Upload to drive
            pdf_link = upload_to_drive(pdf_path, cert_id)

            # Append to Google Sheet
            sheet.append_row([
                cert_id,
                name,
                course,
                datetime.date.today().isoformat(),
                "Verified",
                pdf_link
            ])

if __name__ == "__main__":
    main()