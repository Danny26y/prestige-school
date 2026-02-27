from database import engine
from sqlalchemy import text
import models

def nuke_it_all():
    with engine.connect() as conn:
        print("Executing CASCADE drop...")
        # This tells Postgres: "Delete these tables and anything connected to them!"
        conn.execute(text('DROP TABLE IF EXISTS "User" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "StudentProfile" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "Payment" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "Admission" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "VerifiedJAMB" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "News" CASCADE'))
        conn.commit()
        print("Database wiped clean.")

        print("Rebuilding fresh tables...")
        # Now that the space is clear, build it correctly
        models.Base.metadata.create_all(bind=engine)
        print("All tables recreated with correct columns!")

if __name__ == "__main__":
    nuke_it_all()