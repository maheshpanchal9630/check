from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pymongo import MongoClient

from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware

import qrcode
import os
import uuid
import pdfplumber


# =====================================================
# APP
# =====================================================

app = FastAPI()

# =====================================================
# SESSION
# =====================================================

app.add_middleware(
    SessionMiddleware,
    secret_key="SECRET_KEY",
    same_site="lax",
    https_only=True
)

# =====================================================
# GOOGLE CONFIG
# =====================================================

config_data = {

    "GOOGLE_CLIENT_ID":
    "746534419250-cjt52oodigl73nbtjt799i5l87elcs2f.apps.googleusercontent.com",

    "GOOGLE_CLIENT_SECRET":
    "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"

}

config = Config(environ=config_data)

oauth = OAuth(config)

oauth.register(

    name="google",

    server_metadata_url=
    "https://accounts.google.com/.well-known/openid-configuration",

    client_kwargs={
        "scope": "openid email profile"
    }

)

# =====================================================
# BASE URL
# =====================================================

BASE_URL = "https://YOUR-RENDER-APP.onrender.com"

# =====================================================
# STATIC FILES
# =====================================================

os.makedirs("static/qr", exist_ok=True)

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

# =====================================================
# UPLOADS
# =====================================================

os.makedirs(
    "uploads",
    exist_ok=True
)

# =====================================================
# TEMPLATES
# =====================================================

templates = Jinja2Templates(
    directory="templates"
)

# =====================================================
# DATABASE
# =====================================================

MONGO_URI = "mongodb+srv://mahesh:mahesh123@food-trace-cluster.tpzyr6p.mongodb.net/?retryWrites=true&w=majority&appName=food-trace-cluster"

client = MongoClient(MONGO_URI)

db = client["traceability_db"]

users_col = db["users"]

trace_col = db["trace"]

notification_col = db["notifications"]

# =====================================================
# HOME
# =====================================================

@app.get("/", response_class=HTMLResponse)
def home(request: Request):

    return templates.TemplateResponse(

        request=request,
        name="home.html"

    )

# =====================================================
# SIGNUP
# =====================================================

@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):

    return templates.TemplateResponse(

        request=request,
        name="signup.html"

    )

# =====================================================
# USER PAGE
# =====================================================

@app.get("/user", response_class=HTMLResponse)
def user_page(request: Request):

    return templates.TemplateResponse(

        request=request,
        name="user.html"

    )

# =====================================================
# GOOGLE LOGIN
# =====================================================

@app.get("/google-login")
async def google_login(request: Request):

    redirect_uri = request.url_for(
        "auth"
    )

    return await oauth.google.authorize_redirect(

        request,
        redirect_uri

    )

# =====================================================
# AUTH
# =====================================================

@app.get("/auth")
async def auth(request: Request):

    token = await oauth.google.authorize_access_token(
        request
    )

    user = token.get("userinfo")

    username = user["name"]

    email = user["email"]

    existing_user = users_col.find_one({

        "email": email

    })

    # EXISTING USER

    if existing_user:

        role = existing_user.get("role")

        if not role:

            old_roles = existing_user.get(
                "roles",
                []
            )

            if len(old_roles) > 0:

                role = old_roles[0]

                users_col.update_one(

                    {"email": email},

                    {

                        "$set": {

                            "role": role

                        }

                    }

                )

        return RedirectResponse(

            url=f"/dashboard?user={username}&role={role}",

            status_code=303
        )

    # NEW USER

    request.session["google_user"] = username

    request.session["google_email"] = email

    return RedirectResponse(

        url="/select-role",

        status_code=303
    )

# =====================================================
# ROLE PAGE
# =====================================================

@app.get("/select-role", response_class=HTMLResponse)
def select_role_page(request: Request):

    return templates.TemplateResponse(

        request=request,
        name="select_role.html"

    )

# =====================================================
# SAVE ROLE
# =====================================================

@app.post("/save-role")
def save_role(

    request: Request,

    role: str = Form(...)

):

    username = request.session.get(
        "google_user"
    )

    email = request.session.get(
        "google_email"
    )

    users_col.insert_one({

        "username": username,

        "email": email,

        "role": role,

        "auth_type": "google"

    })

    notification_col.insert_one({

        "user": username,

        "role": role,

        "message": "🎉 Welcome to Smart Traceability System",

        "status": "unread"

    })

    return RedirectResponse(

        url=f"/dashboard?user={username}&role={role}",

        status_code=303
    )

# =====================================================
# DASHBOARD
# =====================================================

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(

    request: Request,
    user: str,
    role: str

):

    batches = list(

        trace_col.find(

            {"updated_by": user},

            {"_id": 0}

        )

    )

    notifications = list(

        notification_col.find(

            {"user": user},

            {"_id": 0}

        )

    )

    return templates.TemplateResponse(

        request=request,

        name="dashboard.html",

        context={

            "user": user,
            "role": role,
            "batches": batches,
            "notifications": notifications

        }

    )

# =====================================================
# ADD TRACE
# =====================================================

@app.post("/add")
def add_trace(

    product: str = Form(...),
    location: str = Form(...),
    date: str = Form(...),
    time: str = Form(...),
    details: str = Form(...),
    updated_by: str = Form(...),

    batchId: str = Form(None),

    seed_date: str = Form(None),
    harvest_date: str = Form(None),
    fertilizer: str = Form(None),

    processing_method: str = Form(None),
    packaging: str = Form(None),

    storage_temp: str = Form(None),
    humidity: str = Form(None),

    vehicle: str = Form(None),
    driver: str = Form(None)

):

    user_data = users_col.find_one({

        "username": updated_by

    })

    role = user_data["role"]

    # FARM CREATE NEW BATCH

    if role == "farm" and (
        batchId is None or batchId == ""
    ):

        batchId = "BATCH-" + str(uuid.uuid4())[:8].upper()

    else:

        existing_batch = trace_col.find_one({

            "batchId": batchId

        })

        if not existing_batch:

            return {

                "message": "Batch not found"

            }

    # QR

    qr_url = f"{BASE_URL}/result?id={batchId}"

    qr_img = qrcode.make(qr_url)

    qr_filename = f"{batchId}.png"

    qr_path = os.path.join(

        "static",
        "qr",
        qr_filename

    )

    qr_img.save(qr_path)

    # SAVE DATA

    trace_col.insert_one({

        "batchId": batchId,

        "product": product,

        "location": location,

        "date": date,

        "time": time,

        "details": details,

        "updated_by": updated_by,

        "role": role,

        "seed_date": seed_date,
        "harvest_date": harvest_date,
        "fertilizer": fertilizer,

        "processing_method": processing_method,
        "packaging": packaging,

        "storage_temp": storage_temp,
        "humidity": humidity,

        "vehicle": vehicle,
        "driver": driver,

        "ai_status": "Pending",
        "ai_reason": "Not analyzed",

        "qr": f"/static/qr/{qr_filename}"

    })

    notification_col.insert_one({

        "user": updated_by,

        "role": role,

        "message": f"📦 Batch {batchId} Updated Successfully",

        "status": "unread"

    })

    return RedirectResponse(

        url=f"/dashboard?user={updated_by}&role={role}",

        status_code=303
    )

# =====================================================
# AI ANALYSIS
# =====================================================

@app.post("/ai-analysis")
async def ai_analysis(

    batchId: str = Form(...),

    report: UploadFile = File(...)

):

    # SAVE FILE

    file_path = f"uploads/{report.filename}"

    with open(file_path, "wb") as f:

        content = await report.read()

        f.write(content)

    extracted_text = ""

    # PDF READ

    if report.filename.endswith(".pdf"):

        with pdfplumber.open(file_path) as pdf:

            for page in pdf.pages:

                text = page.extract_text()

                if text:
                    extracted_text += text

   

    # AI LOGIC

    status = "VERIFIED"

    reason = "Processed product matches farmer batch"

    text_lower = extracted_text.lower()

    if "high chemical" in text_lower:

        status = "NOT VERIFIED"

        reason = "High chemical content detected"

    if "unsafe" in text_lower:

        status = "NOT VERIFIED"

        reason = "Unsafe food detected"

    if "contaminated" in text_lower:

        status = "NOT VERIFIED"

        reason = "Food contamination detected"

    # UPDATE DB

    trace_col.update_one(

        {"batchId": batchId},

        {

            "$set": {

                "ai_status": status,

                "ai_reason": reason,

                "lab_report": report.filename

            }

        }

    )

    batch = trace_col.find_one({

        "batchId": batchId

    })

    # NOTIFICATION

    if status == "VERIFIED":

        message = "🎉 Congratulations! Product Successfully Verified"

    else:

        message = f"⚠ Verification Failed : {reason}"

    notification_col.insert_one({

        "user": batch["updated_by"],

        "role": "factory",

        "message": message,

        "status": "unread"

    })

    return RedirectResponse(

        url=f"/dashboard?user={batch['updated_by']}&role=factory",

        status_code=303
    )

# =====================================================
# RESULT PAGE
# =====================================================

@app.get("/result", response_class=HTMLResponse)
def result(

    request: Request,
    id: str

):

    trace_data = list(

        trace_col.find(

            {"batchId": id},

            {"_id": 0}

        )

    )

    return templates.TemplateResponse(

        request=request,

        name="result.html",

        context={

            "batch": id,
            "trace_data": trace_data

        }

    )

# =====================================================
# HEALTH
# =====================================================

@app.get("/health")
def health():

    return {

        "status": "running"

    }
