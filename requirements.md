1. Project Overview
A professional, institutional-grade portal for the Prestige School of Nursing Benue. The system handles student admissions, professional school announcements, and administrative oversight.

2. Global Design & Aesthetic
Palette: Deep Navy Blue, Medical Teal, and Clean White.

Typography: Inter or Roboto (Google Fonts).

Tone: Clinical, Trustworthy, and Academic.

Responsiveness: Mobile-first design (Critical for students in Benue/Kaduna).

3. Backend Route Mapping (API Contract)
The frontend must interact with these specific endpoints in the main.py file:

🔑 Authentication
Endpoint: POST /login

Format: application/x-www-form-urlencoded

Fields: email, password

Response:

JSON
{
  "id": "uuid-string",
  "email": "user@example.com",
  "role": "student/admin",
  "isPasswordChanged": true
}
Logic: Store id and role in localStorage for session persistence.

📝 Admission Application
Endpoint: POST /apply

Format: multipart/form-data

Fields:

userId (String)

fullName (String)

phoneNumber (String)

stateOfOrigin (String)

passport (File/Image)

results (File/PDF or Image)

Logic: Show a loading spinner during the upload of these high-res files.

📋 Admin Oversight
Endpoint: GET /admin/applications

Logic: Only visible to users with role: admin. Must display a table of all applicants pulled from Neon.

4. Required Pages & Components
A. The Landing Page (index.html)
Hero Section: High-resolution healthcare imagery with "Apply Now" and "Student Portal" buttons.

News Ticker: A dynamic top bar for urgent announcements (e.g., "Exam Date: Oct 12th").

Value Cards: Accreditation, Facilities, and Clinical Practice info.

B. Student Dashboard
Sidebar: Home, Apply, Payment, Profile.

Status Cards: Visual indicator of application progress (Pending, Approved, Rejected).

Identity: Welcome header using the Jinja2 variable {{ user.email }}.

C. Admin Portal
Applicant Table: List of Name, Phone, and links to Passport/Results.

Action Buttons: "Approve" and "Reject" triggers for the ICT team to manage admission flow.

5. Deployment Specs (For ICT Team)
Backend: Python 3.14 (FastAPI).

Server: Truehost (Passenger/WSGI compatible).

Database: PostgreSQL (Neon Cloud).

File Storage: Local /uploads directory (to be migrated to Cloudinary/S3 in the future).