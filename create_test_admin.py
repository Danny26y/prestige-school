import database, models
import bcrypt
import uuid

with database.SessionLocal() as db:
    # ensure course column exists in sqlite test db for this run if not already applied
    from sqlalchemy import text
    try:
        db.execute(text("ALTER TABLE VerifiedJAMB ADD COLUMN course VARCHAR;"))
        db.commit()
    except:
        pass

    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw("AdminPassword2026".encode('utf-8'), salt).decode('utf-8')
    admin = db.query(models.User).filter_by(email="admin@prestige.edu.ng").first()
    if not admin:
        admin = models.User(id=str(uuid.uuid4()), email="admin@prestige.edu.ng", jamb_reg_no="ADMIN", passwordHash=hashed, role="admin")
        db.add(admin)
        db.commit()
