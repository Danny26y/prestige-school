from fastapi import FastAPI, Depends, HTTPException, Form, Request, UploadFile, File, Path
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import bcrypt
import shutil
import os
import uuid
import csv
import io

from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Internal imports
from database import get_db, engine
import models



load_dotenv()

cloudinary.config( 
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
  api_key = os.getenv("CLOUDINARY_API_KEY"), 
  api_secret = os.getenv("CLOUDINARY_API_SECRET") 
)
# --- CONFIGURATION ---
app = FastAPI(title="Prestige School of Nursing API")
templates = Jinja2Templates(directory="templates")

# Mount Static and Upload folders for asset accessibility
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")



# Sync database models with Neon cloud
models.Base.metadata.create_all(bind=engine)

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
    """The Professional Landing Page with Live News and Ticker"""
    # Fetch 3 latest news for the Grid
    news_list = db.query(models.News).order_by(
        models.News.is_urgent.desc(), 
        models.News.created_at.desc()
    ).limit(3).all()

    # Fetch the latest urgent news for the marquee ticker
    latest_news = db.query(models.News).filter(models.News.is_urgent == True).order_by(
        models.News.created_at.desc()
    ).first()
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "news": news_list, 
        "latest_news": latest_news
    })

@app.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def get_register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# --- AUTHENTICATION ACTIONS ---

@app.post("/register")
def register_candidate(
    email: str = Form(...),
    jamb_no: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Verifies JAMB eligibility before allowing registration"""
    jamb_no_upper = jamb_no.strip().upper()

    is_verified = db.query(models.VerifiedJAMB).filter(models.VerifiedJAMB.jamb_no == jamb_no_upper).first()
    if not is_verified:
        raise HTTPException(status_code=403, detail="JAMB Number not found in official list.")

    existing_user = db.query(models.User).filter((models.User.email == email) | (models.User.jamb_reg_no == jamb_no_upper)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Account already exists.")

    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    new_user = models.User(
        id=str(uuid.uuid4()),
        email=email,
        jamb_reg_no=jamb_no_upper,
        passwordHash=hashed_password,
        role="student"
    )

    db.add(new_user)
    db.commit()
    return {"status": "success", "message": f"Welcome, {is_verified.full_name}!"}

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    """Handles secure credential verification and session cookie setting"""
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user.passwordHash.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    response = JSONResponse(content={"id": user.id, "email": user.email, "role": user.role})
    response.set_cookie(key="user_id", value=str(user.id), httponly=True, max_age=86400)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="user_id")
    return response

# --- STUDENT DASHBOARD & APPLICATIONS ---

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user_from_cookie)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    
    if current_user.role == "admin":
        return RedirectResponse(url="/admin", status_code=303)

    application = db.query(models.Admission).filter(models.Admission.userId == current_user.id).first()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "application": application
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
    """Processes file uploads to Cloudinary and saves application records"""
    
    # 1. Upload Passport to Cloudinary
    passport_upload = cloudinary.uploader.upload(
        passport.file, 
        folder="prestige_passports",
        public_id=f"passport_{uuid.uuid4()}"
    )
    passport_secure_url = passport_upload.get("secure_url")

    # 2. Upload Results to Cloudinary
    results_upload = cloudinary.uploader.upload(
        results.file, 
        folder="prestige_results",
        public_id=f"results_{uuid.uuid4()}"
    )
    results_secure_url = results_upload.get("secure_url")

    # 3. Save the Cloud URLs to Neon Database
    new_admission = models.Admission(
        id=str(uuid.uuid4()),
        userId=userId,
        fullName=fullName,
        phoneNumber=phoneNumber,
        stateOfOrigin=stateOfOrigin,
        passportUrl=passport_secure_url, 
        resultsUrl=results_secure_url,   
        status="PENDING"
    )
    db.add(new_admission)
    db.commit()
    return {"status": "success"}

# --- ADMIN CORE ROUTES ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_portal(
    request: Request,
    jamb_search: str = None,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """Admin view for managing student applications"""
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
async def import_jamb_list(file: UploadFile = File(...), db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Bulk imports authorized students from a CSV file"""
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
    """Updates the PENDING/APPROVED/REJECTED status of an applicant"""
    admission = db.query(models.Admission).filter(models.Admission.id == admission_id).first()
    if admission:
        admission.status = status.upper()
        db.commit()
    return {"status": "success"}

# --- NEWS EDITOR & NEWSLETTER ACTIONS ---

@app.get("/admin/news", response_class=HTMLResponse)
async def get_news_editor(request: Request, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Renders the news management dashboard"""
    all_news = db.query(models.News).order_by(models.News.created_at.desc()).all()
    return templates.TemplateResponse("admin_news.html", {"request": request, "news_list": all_news, "admin_user": admin})


@app.post("/admin/news/create")
async def create_news(
    title: str = Form(...), 
    content: str = Form(...), 
    category: str = Form("General"),
    is_urgent: bool = Form(False), 
    image: UploadFile = File(None),
    db: Session = Depends(get_db), 
    admin: models.User = Depends(require_admin)
):
    """Processes new announcements with optional cloud images"""
    image_secure_url = None
    
    # If the admin uploaded an image, send it to Cloudinary
    if image and image.filename:
        news_upload = cloudinary.uploader.upload(
            image.file,
            folder="prestige_news",
            public_id=f"news_{uuid.uuid4()}"
        )
        image_secure_url = news_upload.get("secure_url")

    new_post = models.News(
        title=title, 
        content=content, 
        category=category, 
        is_urgent=is_urgent,
        imageUrl=image_secure_url # Save the Cloudinary URL
    )
    db.add(new_post)
    db.commit()
    
    return RedirectResponse(url="/admin/news", status_code=303)

@app.post("/admin/news/delete/{news_id}")
async def delete_news(
    news_id: str, 
    db: Session = Depends(get_db), 
    admin: models.User = Depends(require_admin)
):
    """Safely removes a post and its physical image from storage"""
    news_item = db.query(models.News).filter(models.News.id == news_id).first()
    
    if not news_item:
        raise HTTPException(status_code=404, detail="News post not found")

    # Clean up physical storage on your Dell laptop
    if news_item.imageUrl and os.path.exists(news_item.imageUrl):
        try:
            os.remove(news_item.imageUrl)
        except Exception as e:
            print(f"File cleanup error: {e}")

    db.delete(news_item)
    db.commit()
    return RedirectResponse(url="/admin/news", status_code=303)
@app.get("/apply", response_class=HTMLResponse)
async def get_apply_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user_from_cookie)):
    # Block unauthorized access
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    
    # Block if they already applied
    existing_app = db.query(models.Admission).filter(models.Admission.userId == current_user.id).first()
    if existing_app:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse("apply.html", {"request": request, "user": current_user})

# --- DIAGNOSTICS ---

@app.get("/ping")
async def ping_test():
    return {"status": "Server is Online"}

@app.get("/profile", response_class=HTMLResponse)
async def get_profile(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user_from_cookie)):
    """Renders the student profile page"""
    # Block unauthorized access
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    
    # If admin somehow gets here, redirect them to admin panel
    if current_user.role == "admin":
        return RedirectResponse(url="/admin", status_code=303)

    # Fetch admission record if it exists to show extra details
    application = db.query(models.Admission).filter(models.Admission.userId == current_user.id).first()

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": current_user,
        "application": application
    })

@app.get("/payment", response_class=HTMLResponse)
async def get_payment_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user_from_cookie)):
    """Renders the coming soon payment portal"""
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    
    if current_user.role == "admin":
        return RedirectResponse(url="/admin", status_code=303)

    return templates.TemplateResponse("payment.html", {"request": request, "user": current_user})