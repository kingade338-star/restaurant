import requests
import hashlib
import hmac
from config import PAYSTACK_SECRET_KEY

PAYSTACK_BASE_URL = "https://api.paystack.co"
YOUR_RENDER_URL = "https://restaurant-9e2l.onrender.com"


def create_payment_link(order_id: int, amount: int, customer_phone: str, customer_name: str = None) -> dict:
    clean_phone = customer_phone.replace("whatsapp:", "").replace("+", "").strip()
    email = f"{clean_phone}@iyameta.com"
    reference = f"IYA-{order_id}-{clean_phone[-6:]}"

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "email": email,
        "amount": amount * 100,
        "reference": reference,
        "callback_url": f"{YOUR_RENDER_URL}/payment/verify",
        "metadata": {
            "order_id": order_id,
            "customer_phone": customer_phone,
            "customer_name": customer_name or "Customer",
            "custom_fields": [
                {"display_name": "Order ID", "variable_name": "order_id", "value": str(order_id)},
                {"display_name": "Phone", "variable_name": "customer_phone", "value": customer_phone}
            ]
        }
    }

    try:
        response = requests.post(
            f"{PAYSTACK_BASE_URL}/transaction/initialize",
            headers=headers,
            json=payload,
            timeout=10
        )
        data = response.json()

        if data.get("status"):
            return {
                "success": True,
                "link": data["data"]["authorization_url"],
                "reference": data["data"]["reference"]
            }
        else:
            print(f"Paystack error: {data}")
            return {"success": False, "error": data.get("message", "Payment link failed")}

    except Exception as e:
        print(f"Payment link error: {e}")
        return {"success": False, "error": str(e)}


def verify_payment(reference: str) -> dict:
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(
            f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
            headers=headers,
            timeout=10
        )
        data = response.json()

        if data.get("status") and data["data"]["status"] == "success":
            metadata = data["data"].get("metadata", {})
            return {
                "paid": True,
                "order_id": metadata.get("order_id"),
                "customer_phone": metadata.get("customer_phone"),
                "customer_name": metadata.get("customer_name"),
                "amount": data["data"]["amount"] // 100,
                "reference": reference
            }
        else:
            return {"paid": False, "error": "Payment not successful"}

    except Exception as e:
        print(f"Verification error: {e}")
        return {"paid": False, "error": str(e)}


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    expected = hmac.new(
        PAYSTACK_SECRET_KEY.encode("utf-8"),
        payload,
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, signature)