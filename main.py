from fastapi import FastAPI, Form, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from twilio.twiml.messaging_response import MessagingResponse
from contextlib import asynccontextmanager
from typing import Optional

from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, ADMIN_PASSWORD
from bot import handle_message, MENU
from database import (
    init_db, get_all_orders, get_all_complaints, get_all_customers,
    get_order_stats, get_order_by_id, get_customer_by_phone, get_customer_history,
    update_order_status, update_complaint_status, get_message_logs
)

# Lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting Iya Meta Bot + Dashboard...")
    init_db()
    print("✅ Database ready!")
    print("📊 Dashboard available at: http://localhost:8000/dashboard")
    yield
    print("🛑 Shutting down...")

# Create app
app = FastAPI(
    title="Iya Meta Restaurant Bot",
    description="WhatsApp Bot with Admin Dashboard",
    version="3.0.0",
    lifespan=lifespan
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ============ WHATSAPP WEBHOOK ============

@app.post("/whatsapp")
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(default="")
):
    """Receive WhatsApp messages from Twilio"""
    print(f"\n{'='*60}")
    print(f"📩 WhatsApp from: {From}")
    print(f"📝 Message: {Body}")
    
    try:
        reply_text = handle_message(Body.strip(), From)
        print(f"🤖 Reply: {reply_text[:100]}...")
    except Exception as e:
        print(f"❌ Error: {e}")
        reply_text = "Sorry, something went wrong. Please try again or call us."
    
    print(f"{'='*60}\n")
    
    # Create Twilio response
    twilio_response = MessagingResponse()
    twilio_response.message(reply_text)
    
    return Response(content=str(twilio_response), media_type="application/xml")

# ============ PUBLIC PAGES ============

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Landing page"""
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "restaurant_name": "Iya Meta",
            "phone": TWILIO_PHONE_NUMBER
        }
    )

@app.get("/menu", response_class=HTMLResponse)
async def public_menu(request: Request):
    """Public menu page"""
    from bot import MENU
    return templates.TemplateResponse(
        request=request,
        name="menu.html",
        context={
            "menu": MENU
        }
    )

# ============ ADMIN DASHBOARD (Password Protected) ============

def verify_password(password: Optional[str] = None):
    """Simple password check"""
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    return True

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, password: Optional[str] = None):
    """Main dashboard with stats"""
    if not password:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={}
        )
    
    verify_password(password)
    
    stats = get_order_stats()
    
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "stats": stats,
            "password": password
        }
    )

@app.get("/dashboard/orders", response_class=HTMLResponse)
async def orders_page(request: Request, password: Optional[str] = None, status: Optional[str] = None):
    """View all orders"""
    verify_password(password)
    
    orders = get_all_orders(status=status, limit=100)
    
    return templates.TemplateResponse(
        request=request,
        name="orders.html",
        context={
            "orders": orders,
            "filter_status": status,
            "password": password
        }
    )

@app.post("/dashboard/orders/{order_id}/update")
async def update_order(order_id: int, status: str = Form(...), notes: Optional[str] = Form(None), password: Optional[str] = None):
    """Update order status"""
    verify_password(password)
    
    update_order_status(order_id, status, notes)
    
    return RedirectResponse(url=f"/dashboard/orders?password={password}", status_code=303)

@app.get("/dashboard/complaints", response_class=HTMLResponse)
async def complaints_page(request: Request, password: Optional[str] = None, status: Optional[str] = None):
    """View all complaints"""
    verify_password(password)
    
    complaints = get_all_complaints(status=status)
    
    return templates.TemplateResponse(
        request=request,
        name="complaints.html",
        context={
            "complaints": complaints,
            "filter_status": status,
            "password": password
        }
    )

@app.post("/dashboard/complaints/{complaint_id}/update")
async def update_complaint(complaint_id: int, status: str = Form(...), resolution: Optional[str] = Form(None), password: Optional[str] = None):
    """Update complaint status"""
    verify_password(password)
    
    update_complaint_status(complaint_id, status, resolution)
    
    return RedirectResponse(url=f"/dashboard/complaints?password={password}", status_code=303)

@app.get("/dashboard/customers", response_class=HTMLResponse)
async def customers_page(request: Request, password: Optional[str] = None):
    """View all customers"""
    verify_password(password)
    
    customers = get_all_customers()
    
    return templates.TemplateResponse(
        request=request,
        name="customers.html",
        context={
            "customers": customers,
            "password": password
        }
    )

@app.get("/dashboard/customer/{phone}", response_class=HTMLResponse)
async def customer_detail(request: Request, phone: str, password: Optional[str] = None):
    """View single customer history"""
    verify_password(password)
    
    customer = get_customer_by_phone(phone)
    history = get_customer_history(phone)
    
    return templates.TemplateResponse(
        request=request,
        name="customer_detail.html",
        context={
            "customer": customer,
            "history": history,
            "password": password
        }
    )

@app.get("/dashboard/messages", response_class=HTMLResponse)
async def messages_page(request: Request, password: Optional[str] = None, phone: Optional[str] = None):
    """View message logs"""
    verify_password(password)
    
    logs = get_message_logs(phone=phone, limit=100)
    
    return templates.TemplateResponse(
        request=request,
        name="messages.html",
        context={
            "logs": logs,
            "filter_phone": phone,
            "password": password
        }
    )


# ============ PAYSTACK PAYMENT WEBHOOK ============

@app.post("/payment/webhook")
async def paystack_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    from payment import verify_webhook_signature, verify_payment
    if not verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    import json as json_lib
    data = json_lib.loads(payload)

    if data.get("event") == "charge.success":
        reference = data["data"]["reference"]
        result = verify_payment(reference)

        if result["paid"]:
            order_id = result["order_id"]
            customer_phone = result["customer_phone"]
            amount = result["amount"]

            update_order_status(order_id, "paid", f"Paid via Paystack ref:{reference}")

            try:
                from twilio.rest import Client
                client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                msg = (
                    f"✅ *Payment Confirmed!*\n\n"
                    f"Order #{order_id} — ₦{amount:,} received.\n\n"
                    f"🍽️ Your food is being prepared now!\n"
                    f"⏰ Ready in 25-30 minutes.\n"
                    f"📍 Farayola Layout, Bodija Market Road, Bodija, Ibadan\n\n"
                    f"Thank you for ordering from Iya Meta! 🙏"
                )
                client.messages.create(
                    from_=TWILIO_PHONE_NUMBER,
                    to=customer_phone,
                    body=msg
                )
            except Exception as e:
                print(f"WhatsApp notification error: {e}")

    return {"status": "ok"}


@app.get("/payment/verify")
async def payment_verify(request: Request, reference: str = ""):
    if not reference:
        return HTMLResponse("<h2>Payment reference missing</h2>")

    from payment import verify_payment
    result = verify_payment(reference)

    if result["paid"]:
        html = f"""<html><body style='font-family:Arial;text-align:center;padding:50px;background:#f5f5f5;'>
        <div style='background:white;padding:40px;border-radius:12px;max-width:500px;margin:auto;'>
        <h1 style='color:#27ae60'>✅ Payment Successful!</h1>
        <p>Order #{result['order_id']} confirmed.</p>
        <p><strong>₦{result['amount']:,}</strong> received.</p>
        <p style='color:#666;margin-top:20px;'>Your food is being prepared.<br>You will get a WhatsApp message shortly.</p>
        <p style='color:#999;font-size:13px;margin-top:20px;'>You can close this page.</p>
        </div></body></html>"""
        return HTMLResponse(html)
    else:
        html = """<html><body style='font-family:Arial;text-align:center;padding:50px;background:#f5f5f5;'>
        <div style='background:white;padding:40px;border-radius:12px;max-width:500px;margin:auto;'>
        <h1 style='color:#e74c3c'>❌ Payment Not Confirmed</h1>
        <p>Please try again or contact the restaurant.</p>
        </div></body></html>"""
        return HTMLResponse(html)

# ============ API ENDPOINTS (JSON) ============

@app.get("/api/stats")
async def api_stats():
    """Get stats as JSON"""
    return get_order_stats()

@app.get("/api/orders")
async def api_orders(status: Optional[str] = None):
    """Get orders as JSON"""
    return get_all_orders(status=status)

@app.get("/api/complaints")
async def api_complaints(status: Optional[str] = None):
    """Get complaints as JSON"""
    return get_all_complaints(status=status)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)