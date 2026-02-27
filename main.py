from fastapi import FastAPI, Depends, HTTPException, Form, Request, UploadFile, File, Path
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
import bcrypt
import shutil
import os
import uuid
import csv
import io

# Internal imports
from database import get_db, engine
import models

# --- CONFIGURATION ---
app = FastAPI(title="Prestige School of Nursing API")
templates = Jinja2Templates(directory="templates")

# Mount Static and Upload folders
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads") # Added this so browser can load images

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Create database tables in Neon (Safe to keep here for dev)
# models.Base.metadata.create_all(bind=engine)

# --- DEPENDENCIES (SESSION MANAGEMENT) ---
def get_current_user_from_cookie(request: Request, db: Session = Depends(get_db)):
    """Extracts the user from the secure browser cookie."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    return db.query(models.User).filter(models.User.id == str(user_id)).first()

def require_admin(user: models.User = Depends(get_current_user_from_cookie)):
    """Strict gatekeeper for ICT Admin routes."""
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Access Denied: Admin Privileges Required.")
    return user

# --- PUBLIC HTML ROUTES ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    """The Professional Landing Page"""
    # Fetch the latest urgent news for the ticker
    latest_news = db.query(models.News).filter(models.News.is_urgent == True).order_by(models.News.created_at.desc()).first()
    return templates.TemplateResponse("index.html", {"request": request, "latest_news": latest_news})

@app.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    """The Login Portal"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def get_register(request: Request):
    """The Registration Portal"""
    return templates.TemplateResponse("register.html", {"request": request})

# --- AUTHENTICATION ACTIONS ---
@app.post("/register")
def register_candidate(
    email: str = Form(...),
    jamb_no: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """JAMB Verification & Account Creation"""
    jamb_no_upper = jamb_no.strip().upper()

    # 1. Check if JAMB is verified
    is_verified = db.query(models.VerifiedJAMB).filter(models.VerifiedJAMB.jamb_no == jamb_no_upper).first()
    if not is_verified:
        raise HTTPException(status_code=403, detail="JAMB Number not found in the official list. Contact ICT.")

    # 2. Check for existing accounts
    existing_user = db.query(models.User).filter((models.User.email == email) | (models.User.jamb_reg_no == jamb_no_upper)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Account with this JAMB number or Email already exists.")

    # 3. Hash Password & Create User
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    new_user = models.User(
        id=str(uuid.uuid4()),
        email=email,
        jamb_reg_no=jamb_no_upper,
        passwordHash=hashed_password,
        role="student",
        isPasswordChanged=False
    )

    db.add(new_user)
    db.commit()
    return {"status": "success", "message": f"Welcome, {is_verified.full_name}! Account created."}

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    """Secure Bcrypt Authentication & Cookie Setting"""
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user.passwordHash.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Prepare response data for JS frontend
    response = JSONResponse(content={"id": user.id, "email": user.email, "role": user.role})
    
    # Set the secure session cookie!
    response.set_cookie(key="user_id", value=str(user.id), httponly=True, max_age=86400) # 24 hour session
    return response

@app.get("/logout")
async def logout():
    """Clears the session cookie and kicks user to login"""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="user_id")
    return response

# --- STUDENT ROUTES ---
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user_from_cookie)):
    """Personalized Student View locked behind cookie"""
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    
    if current_user.role == "admin":
        return RedirectResponse(url="/admin", status_code=303)

    notifications = db.query(models.News).order_by(models.News.created_at.desc()).limit(5).all()
    application = db.query(models.Admission).filter(models.Admission.userId == current_user.id).first()
    status = application.status if application else "Not Started"

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
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
    """Handle High-Res Document Uploads"""
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
    return {"status": "success"}

# --- ADMIN & ICT ROUTES ---
@app.get("/admin", response_class=HTMLResponse)
async def admin_portal(
    request: Request,
    jamb_search: str = None,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """Secure Admin Table"""
    query = db.query(models.Admission)
    if jamb_search:
        query = query.filter(models.Admission.fullName.ilike(f"%{jamb_search}%"))

    apps = query.all()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "applications": apps,
        "admin_user": admin
    })

@app.get("/admin/news", response_class=HTMLResponse)
async def get_news_editor(request: Request, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Secure News Editor"""
    all_news = db.query(models.News).order_by(models.News.created_at.desc()).all()
    return templates.TemplateResponse("admin_news.html", {"request": request, "news_list": all_news, "admin_user": admin})

@app.post("/admin/import-jamb-list")
async def import_jamb_list(file: UploadFile = File(...), db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Bulk CSV Import"""
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
    return {"status": "success", "message": f"Imported {count} students."}

@app.post("/admin/update-status/{admission_id}")
async def update_admission_status(status: str = Form(...), admission_id: str = Path(...), db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Update application logic"""
    admission = db.query(models.Admission).filter(models.Admission.id == admission_id).first()
    if not admission:
        raise HTTPException(status_code=404, detail="Application not found")

    admission.status = status.upper()
    db.commit()
    return {"status": "success"}

@app.post("/news")
async def create_news(
    title: str = Form(...), content: str = Form(...), category: str = Form("General"),
    is_urgent: bool = Form(False), db: Session = Depends(get_db), admin: models.User = Depends(require_admin)
):
    """Creates announcements"""
    new_post = models.News(title=title, content=content, category=category, is_urgent=is_urgent)
    db.add(new_post)
    db.commit()
    return {"status": "success"}

# --- DIAGNOSTICS & UI TESTING ---
@app.get("/audit-db")
def audit_db(db: Session = Depends(get_db)):
    """Neon Health Check"""
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        return {
            "status": "connected",
            "tables": inspector.get_table_names(),
            "user_columns": [c['name'] for c in inspector.get_columns('User')] if 'User' in inspector.get_table_names() else []
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/test-ui/{page}", response_class=HTMLResponse)
async def test_ui(request: Request, page: str):
    """Pure Frontend Viewer"""
    return templates.TemplateResponse(f"{page}.html", {
        "request": request,
        "user": {"email": "test@student.com", "jamb_reg_no": "2026TEST01"},
        "applications": [],
        "application_status": "Pending"
    })
@app.get("/ping")
async def ping_test():
    return {"status": "My Dell is working, the problem is the cloud!"}