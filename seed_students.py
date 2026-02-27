from database import engine, SessionLocal
import models

def seed_test_student():
    db = SessionLocal()
    
    print("Checking for existing test data...")
    test_jamb = "2026TEST01"
    
    # Check if we already seeded this
    exists = db.query(models.VerifiedJAMB).filter_by(jamb_no=test_jamb).first()
    
    if not exists:
        print(f"Adding Verified JAMB Number: {test_jamb}...")
        test_student = models.VerifiedJAMB(
            jamb_no=test_jamb, 
            full_name="Abel Test"
        )
        db.add(test_student)
        db.commit()
        print("Success! You can now go to /register and use JAMB No: 2026TEST01")
    else:
        print("Test student is already in the database!")
        
    db.close()

if __name__ == "__main__":
    seed_test_student()