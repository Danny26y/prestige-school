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
import math
from datetime import datetime, timedelta, timezone
import jwt

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
# app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")



# Sync database models with Neon cloud
models.Base.metadata.create_all(bind=engine)

# --- DEPENDENCIES (SESSION MANAGEMENT) ---

SECRET_KEY = os.getenv("SECRET_KEY", "fallback")
ALGORITHM = "HS256"

def get_current_user_from_cookie(request: Request, db: Session = Depends(get_db)):
    """Extracts the user from the secure browser cookie using JWT."""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return None
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
    except (jwt.ExpiredSignatureError, jwt.PyJWTError):
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

    # Fetch departments
    departments = db.query(models.Department).all()
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "news": news_list, 
        "latest_news": latest_news,
        "departments": departments
    })

@app.get("/news", response_class=HTMLResponse)
async def news_archive(request: Request, page: int = 1, db: Session = Depends(get_db)):
    """Dedicated News Archive Page with Pagination"""
    limit = 6
    offset = (page - 1) * limit

    # Count total
    total_news = db.query(models.News).count()
    total_pages = math.ceil(total_news / limit) if total_news > 0 else 1

    # Fetch paginated items, prioritizing urgent
    news_list = db.query(models.News).order_by(
        models.News.is_urgent.desc(),
        models.News.created_at.desc()
    ).offset(offset).limit(limit).all()

    return templates.TemplateResponse("news_archive.html", {
        "request": request,
        "news": news_list,
        "page": page,
        "total_pages": total_pages
    })

@app.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def get_register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# --- AUTHENTICATION ACTIONS ---

@app.post("/verify-jamb")
def verify_jamb_endpoint(jamb_no: str = Form(...), db: Session = Depends(get_db)):
    """Verifies if a given JAMB Registration Number is authorized."""
    jamb_no_upper = jamb_no.strip().upper()
    is_verified = db.query(models.VerifiedJAMB).filter(models.VerifiedJAMB.jamb_no == jamb_no_upper).first()

    if not is_verified:
        raise HTTPException(status_code=404, detail="JAMB Number not found in official list.")

    return {"status": "success", "full_name": is_verified.full_name, "jamb_no": is_verified.jamb_no}

@app.post("/register")
async def register_candidate(
    email: str = Form(...),
    jamb_no: str = Form(...),
    password: str = Form(...),
    fullName: str = Form(...),
    phoneNumber: str = Form(...),
    stateOfOrigin: str = Form(...),
    passport: UploadFile = File(...),
    results: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Verifies JAMB eligibility, handles file uploads, and creates user + admission record."""
    jamb_no_upper = jamb_no.strip().upper()

    # 1. Verify JAMB eligibility
    is_verified = db.query(models.VerifiedJAMB).filter(models.VerifiedJAMB.jamb_no == jamb_no_upper).first()
    if not is_verified:
        raise HTTPException(status_code=403, detail="JAMB Number not found in official list.")

    # 2. Check for existing user
    existing_user = db.query(models.User).filter((models.User.email == email) | (models.User.jamb_reg_no == jamb_no_upper)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Account already exists.")

    # 3. Validate files
    ALLOWED_TYPES = ["image/jpeg", "image/png", "application/pdf"]
    MAX_SIZE = 2 * 1024 * 1024 # 2MB

    for file_obj, name in [(passport, "Passport"), (results, "Results")]:
        if file_obj.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid file type for {name}. Allowed types: JPEG, PNG, PDF.")

        file_obj.file.seek(0, 2)
        size = file_obj.file.tell()
        file_obj.file.seek(0)

        if size > MAX_SIZE:
            raise HTTPException(status_code=400, detail=f"{name} file size exceeds 2MB limit.")

    try:
        # 4. Upload to Cloudinary
        passport_upload = cloudinary.uploader.upload(
            passport.file,
            folder="prestige_passports",
            resource_type="image"
        )

        # Results could be pdf or image
        resource_type = "image"
        if results.content_type == "application/pdf":
            resource_type = "raw"

        results_upload = cloudinary.uploader.upload(
            results.file,
            folder="prestige_results",
            resource_type=resource_type
        )
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload files. Please try again.")

    # 5. Create User and Admission
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
    db.flush() # flush to get the user ID

    new_admission = models.Admission(
        userId=new_user.id,
        fullName=fullName,
        phoneNumber=phoneNumber,
        stateOfOrigin=stateOfOrigin,
        passportUrl=passport_upload.get('secure_url'),
        resultsUrl=results_upload.get('secure_url'),
        status="PENDING"
    )
    db.add(new_admission)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        # Clean up uploaded files if DB commit fails
        try:
            cloudinary.uploader.destroy(passport_upload.get('public_id'))
            cloudinary.uploader.destroy(results_upload.get('public_id'), resource_type=resource_type)
        except:
            pass
        raise HTTPException(status_code=500, detail="Failed to create account due to a database error.")

    return {"status": "success", "message": f"Welcome, {is_verified.full_name}! Application submitted."}

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    """Handles secure credential verification and session cookie setting"""
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user.passwordHash.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(days=1)},
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    response = JSONResponse(content={"id": user.id, "email": user.email, "role": user.role})
    response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=86400)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="access_token")
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

@app.get("/dashboard/print-letter", response_class=HTMLResponse)
async def print_admission_letter(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user_from_cookie)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    application = db.query(models.Admission).filter(models.Admission.userId == current_user.id).first()

    if not application or application.status != "APPROVED":
        raise HTTPException(status_code=403, detail="You do not have an approved admission to print.")

    return templates.TemplateResponse("admission_letter.html", {
        "request": request,
        "user": current_user,
        "application": application,
        "date": datetime.now().strftime("%B %d, %Y")
    })

@app.post("/apply")
async def apply_for_admission(
    userId: str = Form(...),
    fullName: str = Form(...),
    phoneNumber: str = Form(...),
    stateOfOrigin: str = Form(...),
    course: str = Form("ND Community Health"),
    passport: UploadFile = File(...),
    results: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Processes file uploads to Cloudinary and saves application records"""
    
    ALLOWED_TYPES = ["image/jpeg", "image/png", "application/pdf"]
    MAX_SIZE = 2 * 1024 * 1024 # 2MB

    for file_obj, name in [(passport, "Passport"), (results, "Results")]:
        if file_obj.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid file type for {name}. Allowed types: JPEG, PNG, PDF.")

        file_obj.file.seek(0, 2)
        size = file_obj.file.tell()
        file_obj.file.seek(0)

        if size > MAX_SIZE:
            raise HTTPException(status_code=400, detail=f"{name} file size exceeds 2MB limit.")

    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred while uploading files. Please try again.")

    # 3. Save the Cloud URLs to Neon Database
    new_admission = models.Admission(
        id=str(uuid.uuid4()),
        userId=userId,
        fullName=fullName,
        phoneNumber=phoneNumber,
        stateOfOrigin=stateOfOrigin,
        course=course,
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
    decoded_content = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded_content))

    # Normalize headers to lowercase and strip whitespace to handle standard JAMB CAPS export formats
    reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]

    count = 0
    for row in reader:
        raw_jamb_no = row.get('jamb_no') or row.get('jamb registration number') or row.get('reg_no')
        if not raw_jamb_no:
            continue
        jamb_no = str(raw_jamb_no).strip().upper()
        full_name = row.get('full_name') or row.get('candidate name') or row.get('name', '')

        if not db.query(models.VerifiedJAMB).filter_by(jamb_no=jamb_no).first():
            new_entry = models.VerifiedJAMB(jamb_no=jamb_no, full_name=full_name)
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
    """Safely removes a post and its cloud image from storage"""
    news_item = db.query(models.News).filter(models.News.id == news_id).first()
    
    if not news_item:
        raise HTTPException(status_code=404, detail="News post not found")

    # Clean up cloud storage
    if news_item.imageUrl:
        try:
            # Extract public_id from Cloudinary URL: e.g. .../upload/v12345/folder/id.extension
            # Assuming standard Cloudinary URLs, the public_id includes the folder structure
            parts = news_item.imageUrl.split('/')
            if 'upload' in parts:
                upload_index = parts.index('upload')
                # Join the parts after upload (excluding version if it exists, though usually it's 'v' followed by digits)
                # For simplicity, we can extract everything after upload/v.../ or upload/ up to the extension
                path_parts = parts[upload_index+1:]
                if path_parts[0].startswith('v') and path_parts[0][1:].isdigit():
                    path_parts = path_parts[1:]

                file_with_ext = "/".join(path_parts)
                public_id = file_with_ext.rsplit('.', 1)[0]
                cloudinary.uploader.destroy(public_id)
        except Exception as e:
            print(f"Cloudinary cleanup error: {e}")

    db.delete(news_item)
    db.commit()
    return RedirectResponse(url="/admin/news", status_code=303)


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
    """Renders the payment portal with calculated fees based on admitted course"""
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    
    if current_user.role == "admin":
        return RedirectResponse(url="/admin", status_code=303)

    application = db.query(models.Admission).filter(models.Admission.userId == current_user.id).first()

    fee = 50000 # Default
    course = "Not Selected"
    if application:
        course = application.course
        if course == "ND Medical Laboratory":
            fee = 60000
        else:
            fee = 50000

    return templates.TemplateResponse("payment.html", {
        "request": request,
        "user": current_user,
        "application": application,
        "fee": fee,
        "course": course
    })

@app.post("/payment/initialize")
async def initialize_payment(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user_from_cookie)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    application = db.query(models.Admission).filter(models.Admission.userId == current_user.id).first()
    fee = 50000
    if application and application.course == "ND Medical Laboratory":
        fee = 60000

    reference = f"REF-{uuid.uuid4().hex}"

    # In a real scenario, you'd call Paystack API here and get an authorization URL.
    return {"status": "success", "reference": reference, "amount": fee}