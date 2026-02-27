from database import engine
import models

def permanent_fix():
    print("Step 1: Wiping the old structure...")
    models.Base.metadata.drop_all(bind=engine)
    
    print("Step 2: Building the final structure...")
    # This reads your models.py and builds EVERY column correctly
    models.Base.metadata.create_all(bind=engine)
    
    print("Step 3: Database is now permanently synchronized!")

if __name__ == "__main__":
    permanent_fix()