from fastapi import FastAPI, Depends, HTTPException, Form, Request, UploadFile, File, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
import bcrypt
import shutil
import os
import uuid

# Internal imports
from database import get_db, engine
import models

# --- CONFIGURATION ---
app = FastAPI(title="Prestige School of Nursing API")
templates = Jinja2Templates(directory="templates")

# Mount Static and Upload folders
app.mount("/static", StaticFiles(directory="static"), name="static")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Create database tables in Neon
models.Base.metadata.create_all(bind=engine)

# --- DEPENDENCIES ---
def get_current_user(db: Session = Depends(get_db)):
    """Injected logic to remove placeholders and fetch real user data"""
    user = db.query(models.User).first() # Fallback for initial dev
    if not user:
        raise HTTPException(status_code=404, detail="No user found")
    return user

# --- PUBLIC ROUTES ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """The Professional Landing Page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    """The Login Portal"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    """Secure Bcrypt Authentication"""
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    password_bytes = password.encode('utf-8')
    hashed_bytes = user.passwordHash.encode('utf-8')

    if not bcrypt.checkpw(password_bytes, hashed_bytes):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "isPasswordChanged": user.isPasswordChanged
    }

# --- STUDENT ROUTES ---
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Personalized Student View (No Placeholders)"""
    notifications = db.query(models.News).order_by(models.News.created_at.desc()).limit(5).all()
    application = db.query(models.Admission).filter(models.Admission.userId == current_user.id).first()
    status = application.status if application else "Not Started"

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "school_name": "Prestige School of Nursing",
        "user": current_user,
        "notifications": notifications,
        "application_status": status
    })

@app.post("/apply")
async def apply_for_admission(
    userId: str = Form(...),
    fullName: str = Form(...),
    phoneNumber: str = Form(...),
    stateOfOrigin: str = Form(...),
    passport: UploadFile = File(...),
    results: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Handle File Uploads to Disk and Metadata to Neon"""
    passport_filename = f"{uuid.uuid4()}_{passport.filename}"
    results_filename = f"{uuid.uuid4()}_{results.filename}"
    passport_path = os.path.join(UPLOAD_DIR, passport_filename)
    results_path = os.path.join(UPLOAD_DIR, results_filename)

    with open(passport_path, "wb") as buffer:
        shutil.copyfileobj(passport.file, buffer)
    with open(results_path, "wb") as buffer:
        shutil.copyfileobj(results.file, buffer)

    new_admission = models.Admission(
        id=str(uuid.uuid4()),
        userId=userId,
        fullName=fullName,
        phoneNumber=phoneNumber,
        stateOfOrigin=stateOfOrigin,
        passportUrl=passport_path,
        resultsUrl=results_path,
        status="PENDING"
    )
    db.add(new_admission)
    db.commit()
    return {"status": "success", "applicationId": new_admission.id}


# --- ADMIN & ICT ROUTES ---

# Security Configuration: Replace with the actual School Public IP
ALLOWED_SCHOOL_IPS = ["192.168.1.1", "102.89.0.1"]


def verify_admin_access(request: Request, current_user: models.User = Depends(get_current_user)):
    """Security Layer: Checks both User Role and School Network IP"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access Denied: Admin Privileges Required.")

    client_ip = request.client.host
    # Note: During local development, client_ip might be "127.0.0.1"
    if client_ip not in ALLOWED_SCHOOL_IPS and client_ip != "127.0.0.1":
        raise HTTPException(status_code=403, detail="Access Restricted to School Network.")
    return current_user


@app.get("/admin", response_class=HTMLResponse)
async def admin_portal(
        request: Request,
        jamb_search: str = None,
        db: Session = Depends(get_db),
        admin: models.User = Depends(verify_admin_access)
):
    """Main Oversight Portal with Search Functionality"""
    query = db.query(models.Admission)
    if jamb_search:
        query = query.filter(models.Admission.fullName.ilike(f"%{jamb_search}%"))

    apps = query.all()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "applications": apps,
        "admin_user": admin
    })


@app.post("/admin/import-jamb-list")
async def import_jamb_list(
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        admin: models.User = Depends(verify_admin_access)
):
    """Bulk Import Logic for JAMB-provided Admission Lists"""
    import csv, io
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode('utf-8')))

    count = 0
    for row in reader:
        jamb_no = row.get('jamb_no').strip().upper()
        if not db.query(models.VerifiedJAMB).filter_by(jamb_no=jamb_no).first():
            new_entry = models.VerifiedJAMB(jamb_no=jamb_no, full_name=row.get('full_name'))
            db.add(new_entry)
            count += 1
    db.commit()
    return {"status": "success", "message": f"Imported {count} verified candidates."}


@app.post("/admin/update-status/{admission_id}")
async def update_admission_status(
        status: str = Form(...),
        admission_id: str = Path(...),
        db: Session = Depends(get_db),
        admin: models.User = Depends(verify_admin_access)
):
    """Approve or Reject Student Applications"""
    admission = db.query(models.Admission).filter(models.Admission.id == admission_id).first()
    if not admission:
        raise HTTPException(status_code=404, detail="Application not found")

    admission.status = status.upper()
    db.commit()
    return {"status": "success", "new_state": admission.status}


@app.post("/news")
async def create_news(
        title: str = Form(...),
        content: str = Form(...),
        category: str = Form("General"),
        is_urgent: bool = Form(False),
        db: Session = Depends(get_db),
        admin: models.User = Depends(verify_admin_access)
):
    """Institutional Announcements for Landing Page"""
    new_post = models.News(title=title, content=content, category=category, is_urgent=is_urgent)
    db.add(new_post)
    db.commit()
    return {"status": "success", "news_id": new_post.id}
@app.get("/admin/news", response_class=HTMLResponse)
async def get_news_editor(
    request: Request,
    db: Session = Depends(get_db),
    admin: models.User = Depends(verify_admin_access)
):
    """
    Serves the News Editor page.
    Only accessible via School Network IP and Admin Role.
    """
    # Fetch existing news so the ICT team can see/manage previous posts
    all_news = db.query(models.News).order_by(models.News.created_at.desc()).all()

    return templates.TemplateResponse("admin_news.html", {
        "request": request,
        "news_list": all_news,
        "admin_user": admin
    })
# --- DIAGNOSTICS ---
@app.get("/audit-db")
def audit_db(db: Session = Depends(get_db)):
    """Neon Database Health Check"""
    try:
        result = db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        return {"status": "connected", "detected_tables": [row[0] for row in result]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/register")
def register_candidate(
    email: str = Form(...),
    jamb_no: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # 1. Normalize the JAMB Number (uppercase to match CSV imports)
    jamb_no_upper = jamb_no.strip().upper()

    # 2. STEP ONE: Check if this JAMB number is in the official list uploaded by ICT
    # This prevents unauthorized users from creating accounts
    is_verified = db.query(models.VerifiedJAMB).filter(
        models.VerifiedJAMB.jamb_no == jamb_no_upper
    ).first()

    if not is_verified:
        raise HTTPException(
            status_code=403,
            detail="Your JAMB Number was not found in the official admission list. Please contact the ICT department."
        )

    # 3. STEP TWO: Check if an account already exists for this Email or JAMB No
    existing_user = db.query(models.User).filter(
        (models.User.email == email) | (models.User.jamb_reg_no == jamb_no_upper)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="An account with this JAMB number or Email already exists."
        )

    # 4. STEP THREE: Securely hash the password
    # We use bcrypt to protect student credentials
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    # 5. STEP FOUR: Create the user record in Neon
    new_user = models.User(
        id=str(uuid.uuid4()), # Unique internal ID
        email=email,
        jamb_reg_no=jamb_no_upper,
        passwordHash=hashed_password,
        role="student",
        isPasswordChanged=False
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error during registration.")

    return {
        "status": "success",
        "message": f"Welcome, {is_verified.full_name}! Your account has been created successfully."
    }

import csv
import io


@app.post("/admin/import-jamb-list")
async def import_jamb_list(
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    # 1. Security check: Only ICT Admins can upload this list
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized")

    # 2. Read the CSV file
    content = await file.read()
    decoded = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))

    # 3. Process each row
    count = 0
    for row in reader:
        # Assuming CSV headers are: jamb_no, full_name
        jamb_no = row.get('jamb_no').strip().upper()

        # Check if already in our verified list to avoid duplicates
        exists = db.query(models.VerifiedJAMB).filter(models.VerifiedJAMB.jamb_no == jamb_no).first()

        if not exists:
            new_entry = models.VerifiedJAMB(
                jamb_no=jamb_no,
                full_name=row.get('full_name')
            )
            db.add(new_entry)
            count += 1

    db.commit()
    return {"status": "success", "message": f"Imported {count} students from JAMB list."}
from fastapi import Request

# Replace your previous get_current_user logic with this:
ALLOWED_SCHOOL_IPS = ["192.168.1.1", "102.89.0.1"] # Replace with the actual School Public IP

def get_admin_user(request: Request, db: Session = Depends(get_db)):
    # 1. Check IP Address
    client_ip = request.client.host
    if client_ip not in ALLOWED_SCHOOL_IPS:
        raise HTTPException(status_code=403, detail="Admin access restricted to School Network.")

    # 2. Check User Identity
    # For now, we pull the user (later this will be from a JWT token)
    user = db.query(models.User).filter(models.User.role == "admin").first()
    if not user:
         raise HTTPException(status_code=401, detail="Admin account required.")
    return user
