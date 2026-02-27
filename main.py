from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import bcrypt
import shutil
import os
import uuid
from fastapi import UploadFile, File
# Internal imports
from database import get_db,engine
import models
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
from fastapi.staticfiles import StaticFiles



templates = Jinja2Templates(directory="templates")



app = FastAPI(title="Prestige School of Nursing API")
# This line is the missing link
app.mount("/static", StaticFiles(directory="static"), name="static")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


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
    # 1. Ensure directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 2. Create unique filenames
    passport_filename = f"{uuid.uuid4()}_{passport.filename}"
    results_filename = f"{uuid.uuid4()}_{results.filename}"

    passport_path = os.path.join(UPLOAD_DIR, passport_filename)
    results_path = os.path.join(UPLOAD_DIR, results_filename)

    # 3. Write files to disk
    try:
        with open(passport_path, "wb") as buffer:
            shutil.copyfileobj(passport.file, buffer)
        with open(results_path, "wb") as buffer:
            shutil.copyfileobj(results.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

    # 4. Save to Neon
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
    db.refresh(new_admission)

    return {"status": "success", "applicationId": new_admission.id}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # This serves the actual landing page
    return templates.TemplateResponse("index.html", {"request": request})

models.Base.metadata.create_all(bind=engine)
@app.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # 1. Look for user by email
    # Note: Ensure models.User matches the table name "User" in Neon
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    try:
        # 2. Direct bcrypt verification (Bypasses passlib bugs)
        # We encode strings to bytes before checking
        password_bytes = password.encode('utf-8')
        hashed_bytes = user.passwordHash.encode('utf-8')

        if not bcrypt.checkpw(password_bytes, hashed_bytes):
            raise HTTPException(status_code=400, detail="Invalid credentials")

    except Exception as e:
        # This catches issues like improperly formatted hashes in the DB
        print(f"Bcrypt error: {e}")
        raise HTTPException(status_code=500, detail="Internal authentication error")

    # 3. Success response
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "isPasswordChanged": user.isPasswordChanged
    }


@app.get("/audit-db")
def audit_db(db: Session = Depends(get_db)):
    """Diagnostic route to verify Neon DB connection and table structure"""
    try:
        # Get list of all tables in the public schema
        result = db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        tables = [row[0] for row in result]

        # Get column names for the User table specifically
        columns_query = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='User'"))
        columns = [row[0] for row in columns_query]

        return {
            "status": "connected",
            "detected_tables": tables,
            "user_table_columns": columns
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    # We are passing a fake 'user' object so the template doesn't crash
    # Later, we will get this from the actual logged-in user
    user_data = {"email": "admin@prestige.edu.ng"}

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "school_name": "Prestige School of Nursing",
        "user": user_data,  # This fixes the UndefinedError
        "application_status": "Pending"
    })
@app.get("/admin/applications", response_class=HTMLResponse)
async def admin_portal(request: Request, db: Session = Depends(get_db)):
    # Pull real applications from your Neon DB
    apps = db.query(models.Admission).all()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "applications": apps
    })