import os
import bcrypt
from dotenv import load_dotenv
from database import SessionLocal
import models

load_dotenv()

def create_initial_admin():
    db = SessionLocal()
    # Check if admin already exists
    if db.query(models.User).filter(models.User.role == "admin").first():
        print("Admin already exists.")
        return

    admin_password = os.getenv("ADMIN_PASSWORD", "AdminPassword2026")
    hashed = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    admin = models.User(
        email="admin@prestigesoh.com.ng",
        passwordHash=hashed,
        role="admin",
        isPasswordChanged=False
    )
    db.add(admin)
    db.commit()
    print("ICT Admin Created.")

if __name__ == "__main__":
    create_initial_admin()