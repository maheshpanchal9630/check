# =====================================================
# app.py
# COMPLETE UPDATED VERSION
# =====================================================

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pymongo import MongoClient
from datetime import datetime
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware

from blockchain import compute_hash, verify_chain

import qrcode
import os
import uuid

# =====================================================
# APP
# =====================================================

app = FastAPI()

# =====================================================
# SESSION
# =====================================================

app.add_middleware(
    SessionMiddleware,
    secret_key="mysecretkey",
    same_site="lax",
    https_only=False
)

# =====================================================
# GOOGLE AUTH
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

BASE_URL = "http://127.0.0.1:8000"

# =====================================================
# CREATE FOLDERS
# =====================================================

os.makedirs("static/qr", exist_ok=True)

# =====================================================
# STATIC
# =====================================================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
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
# USER PAGE
# =====================================================

@app.get("/user", response_class=HTMLResponse)
def user_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="user.html"
    )

# =====================================================
# SIGNUP PAGE
# =====================================================

@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="signup.html"
    )

# =====================================================
# NORMAL SIGNUP
# =====================================================

@app.post("/signup")
def normal_signup(

    username: str = Form(...),
    email: str = Form(...),
    role: str = Form(...)

):

    existing_user = users_col.find_one({
        "email": email
    })

    if existing_user:

        return JSONResponse(
            content={
                "message": "User already exists"
            },
            status_code=400
        )

    users_col.insert_one({

        "username": username,
        "email": email,
        "role": role

    })

    notification_col.insert_one({

        "user": username,
        "message": "Account Created Successfully"

    })

    return RedirectResponse(

        url=f"/dashboard?user={username}&role={role}",

        status_code=303
    )

# =====================================================
# GOOGLE LOGIN
# =====================================================

@app.get("/google-login")
async def google_login(request: Request):

    redirect_uri = request.url_for("auth")

    return await oauth.google.authorize_redirect(
        request,
        redirect_uri
    )

# =====================================================
# AUTH CALLBACK
# =====================================================

@app.get("/auth")
async def auth(request: Request):

    try:

        token = await oauth.google.authorize_access_token(
            request
        )

        user = token.get("userinfo")

        username = user["name"]

        email = user["email"]

        existing_user = users_col.find_one({
            "email": email
        })

        if existing_user:

            role = existing_user.get("role")

            return RedirectResponse(
                url=f"/dashboard?user={username}&role={role}",
                status_code=303
            )

        request.session["google_user"] = username
        request.session["google_email"] = email

        return RedirectResponse(
            url="/select-role",
            status_code=303
        )

    except Exception as e:

        return JSONResponse(
            content={
                "error": str(e)
            },
            status_code=500
        )

# =====================================================
# SELECT ROLE
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

    if not username or not email:

        return RedirectResponse(
            "/signup",
            status_code=303
        )

    users_col.insert_one({

    "username": username,

    "email": email,

    "role": role,

    "created_at": datetime.utcnow()

})

    notification_col.insert_one({

        "user": username,
        "message": "Welcome To Smart Traceability System"

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

    user_batches = list(

        trace_col.find(
            {"updated_by": user},
            {"_id": 0}
        )

    )

    batch_ids = list(set(
        [x["batchId"] for x in user_batches]
    ))

    final_batches = []

    for batch_id in batch_ids:

        records = list(

            trace_col.find(
                {"batchId": batch_id},
                {"_id": 0}
            )

        )

        blockchain_status = verify_chain(records)

        latest = records[-1]

        latest["blockchain_valid"] = blockchain_status["valid"]

        latest["blockchain_message"] = blockchain_status["message"]

        final_batches.append(latest)

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
            "batches": final_batches,
            "notifications": notifications

        }

    )

# =====================================================
# ADD TRACE
# =====================================================

@app.post("/add")
def add_trace(

    request: Request,

    product: str = Form(""),
    location: str = Form(""),
    date: str = Form(""),
    time: str = Form(""),
    details: str = Form(""),
    updated_by: str = Form(""),
    batchId: str = Form(None),

    farmer_name: str = Form(None),
    crop_name: str = Form(None),
    crop_type: str = Form(None),
    pesticides: str = Form(None),
    fertilizer: str = Form(None),
    harvest_date: str = Form(None),

    factory_name: str = Form(None),
    packaging: str = Form(None),

    agency_name: str = Form(None),
    destination: str = Form(None),
    vehicle: str = Form(None),
    driver: str = Form(None),

    warehouse_name: str = Form(None),
    storage_temp: str = Form(None),
    shelf: str = Form(None),
    humidity: str = Form(None),

    shop_name: str = Form(None),
    price: str = Form(None),
    expiry_date: str = Form(None)

):

    user_data = users_col.find_one({
        "username": updated_by
    })

    if not user_data:

        return JSONResponse(
            content={
                "message": "User not found"
            },
            status_code=404
        )

    role = user_data["role"]

    # =====================================================
    # CREATE NEW BATCH
    # =====================================================

    if role == "farm":

        batchId = "BATCH-" + str(uuid.uuid4())[:8].upper()

    else:

        existing_batch = trace_col.find_one({
            "batchId": batchId
        })

        if not existing_batch:

            return JSONResponse(
                content={
                    "message": "Batch not found"
                },
                status_code=404
            )

    # =====================================================
    # BLOCK NUMBER
    # =====================================================

    last_block = trace_col.count_documents({
        "batchId": batchId
    })

    block_number = last_block + 1

    # =====================================================
    # PREVIOUS HASH
    # =====================================================

    previous_record = trace_col.find_one(
        {"batchId": batchId},
        sort=[("_id", -1)]
    )

    prev_hash = "0" * 64

    if previous_record:

        old_hash = previous_record.get("hash")

        if old_hash:

            prev_hash = old_hash

    # =====================================================
    # HASH DATA
    # =====================================================

    hash_data = {

        "product": product,
        "location": location,
        "date": date,
        "time": time,
        "details": details,
        "updated_by": updated_by,
        "role": role,
        "block_number": block_number

    }

    current_hash = compute_hash(
        hash_data,
        prev_hash
    )

    # =====================================================
    # QR CODE
    # =====================================================

    qr_url = f"{BASE_URL}/result?id={batchId}"

    qr_img = qrcode.make(qr_url)

    qr_filename = f"{batchId}.png"

    qr_path = os.path.join(
        "static/qr",
        qr_filename
    )

    qr_img.save(qr_path)

    # =====================================================
    # SAVE DATABASE
    # =====================================================

    trace_col.insert_one({

        "batchId": batchId,

        "product": product,
        "location": location,
        "date": date,
        "time": time,
        "details": details,

        "updated_by": updated_by,
        "role": role,

        "farmer_name": farmer_name,
        "crop_name": crop_name,
        "crop_type": crop_type,
        "pesticides": pesticides,
        "fertilizer": fertilizer,
        "harvest_date": harvest_date,

        "factory_name": factory_name,
        "packaging": packaging,

        "agency_name": agency_name,
        "destination": destination,
        "vehicle": vehicle,
        "driver": driver,

        "warehouse_name": warehouse_name,
        "storage_temp": storage_temp,
        "shelf": shelf,
        "humidity": humidity,

        "shop_name": shop_name,
        "price": price,
        "expiry_date": expiry_date,

        "block_number": block_number,
        "hash": current_hash,
        "prev_hash": prev_hash,

        "status": "Verified",
        "created_at": datetime.utcnow(),
        "qr": f"/static/qr/{qr_filename}"

    })

    notification_col.insert_one({

        "user": updated_by,

        "message": f"{role.upper()} updated batch {batchId}"

    })

    return RedirectResponse(

        url=f"/dashboard?user={updated_by}&role={role}",

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

    chain_status = verify_chain(trace_data)

    return templates.TemplateResponse(

        request=request,

        name="result.html",

        context={

            "batch": id,
            "trace_data": trace_data,
            "chain_status": chain_status

        }

    )

# =====================================================
# VERIFY BLOCKCHAIN
# =====================================================

@app.get("/verify/{batch_id}")
def verify(batch_id: str):

    trace_data = list(

        trace_col.find(
            {"batchId": batch_id},
            {"_id": 0}
        )

    )

    result = verify_chain(trace_data)

    return result

# =====================================================
# PROFILE PAGE
# =====================================================

@app.get("/profile", response_class=HTMLResponse)
def profile(

    request: Request,
    user: str

):

    user_data = users_col.find_one(
        {"username": user},
        {"_id": 0}
    )

    return templates.TemplateResponse(

        request=request,

        name="profile.html",

        context={

            "profile": user_data

        }

    )

# =====================================================
# NOTIFICATIONS PAGE
# =====================================================

@app.get("/notifications", response_class=HTMLResponse)
def notifications(

    request: Request,
    user: str

):

    notifications = list(

        notification_col.find(
            {"user": user},
            {"_id": 0}
        )

    )

    return templates.TemplateResponse(

        request=request,

        name="notifications.html",

        context={

            "notifications": notifications,
            "user": user

        }

    )

# =====================================================
# MY BATCHES PAGE
# =====================================================

@app.get("/my-batches", response_class=HTMLResponse)
def my_batches(

    request: Request,
    user: str

):

    batches = list(

        trace_col.find(
            {"updated_by": user},
            {"_id": 0}
        )

    )

    return templates.TemplateResponse(

        request=request,

        name="my_batches.html",

        context={

            "batches": batches,
            "user": user

        }

    )

# =====================================================
# VERIFY BLOCKCHAIN PAGE
# =====================================================

@app.get("/verify-blockchain/{batch_id}",
         response_class=HTMLResponse)

def verify_blockchain_page(

    request: Request,
    batch_id: str

):

    trace_data = list(

        trace_col.find(
            {"batchId": batch_id},
            {"_id": 0}
        )

    )

    result = verify_chain(trace_data)

    return templates.TemplateResponse(

        request=request,

        name="verify_blockchain.html",

        context={

            "result": result,
            "batch": batch_id

        }

    )

# =====================================================
# SETTINGS PAGE
# =====================================================

@app.get("/settings", response_class=HTMLResponse)
def settings(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="settings.html"
    )

# =====================================================
# LOGOUT
# =====================================================

@app.get("/logout")
def logout(request: Request):

    request.session.clear()

    return RedirectResponse(
        url="/",
        status_code=303
    )

# =====================================================
# HEALTH
# =====================================================

@app.get("/health")
def health():

    return {
        "status": "running"
    }

# =====================================================
# START
# =====================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
