# ============================================
# IYA META BOT - COMPLETE FILE
# ============================================

# CONFIGURATION - UPDATE THESE
RESTAURANT_NAME = "Iya Meta"
RESTAURANT_PHONE = "+14155238886"  # Your Twilio/WhatsApp number
RESTAURANT_ADDRESS = "Farayola Layout, Bodija Market Road, Bodija, Ibadan"
OPENING_HOURS = "Monday-Sunday: 8:00 AM - 10:00 PM"
DELIVERY_FEE = 1000

# IMPORTS
import json
import requests
from typing import Dict, Any, Optional
from config import GROQ_API_KEY, TWILIO_PHONE_NUMBER
from database import (
    save_order, save_complaint, update_customer_state,
    get_customer_state, get_customer_by_phone, log_message
)

# MENU - 20 NIGERIAN DISHES
MENU = {
    "1": {"name": "Jollof Rice + Chicken", "price": 2500, "category": "Rice Dishes"},
    "2": {"name": "Fried Rice + Beef", "price": 2300, "category": "Rice Dishes"},
    "3": {"name": "Ofada Rice + Ayamase", "price": 2800, "category": "Rice Dishes"},
    "4": {"name": "White Rice + Egusi Soup", "price": 2200, "category": "Rice Dishes"},
    "5": {"name": "Pounded Yam + Efo Riro", "price": 2000, "category": "Swallows"},
    "6": {"name": "Amala + Gbegiri & Ewedu", "price": 1800, "category": "Swallows"},
    "7": {"name": "Semo + Ogbono Soup", "price": 2000, "category": "Swallows"},
    "8": {"name": "Eba + Afang Soup", "price": 2200, "category": "Swallows"},
    "9": {"name": "Grilled Catfish", "price": 3500, "category": "Proteins"},
    "10": {"name": "Fried Goat Meat (5pcs)", "price": 2000, "category": "Proteins"},
    "11": {"name": "Peppered Chicken", "price": 2200, "category": "Proteins"},
    "12": {"name": "Nkwobi", "price": 2500, "category": "Proteins"},
    "13": {"name": "Puff Puff (10pcs)", "price": 1000, "category": "Small Chops"},
    "14": {"name": "Meat Pie", "price": 800, "category": "Small Chops"},
    "15": {"name": "Chin Chin", "price": 600, "category": "Small Chops"},
    "16": {"name": "Spring Rolls (4pcs)", "price": 1200, "category": "Small Chops"},
    "17": {"name": "Chapman", "price": 1000, "category": "Drinks"},
    "18": {"name": "Zobo", "price": 600, "category": "Drinks"},
    "19": {"name": "Fresh Palm Wine", "price": 1500, "category": "Drinks"},
    "20": {"name": "Bottled Water", "price": 300, "category": "Drinks"}
}

# ============================================
# WELCOME MESSAGE
# ============================================

def get_welcome_message() -> str:
    return (
        f"👋 Welcome to *{RESTAURANT_NAME}*!\n\n"
        f"Here's how to get started:\n\n"
        f"🍽️ *TO ORDER FOOD*\n"
        f"1️⃣ Type *MENU* to see all our dishes\n"
        f"2️⃣ Reply with numbers e.g. *1, 3, 5* to select\n"
        f"3️⃣ Type *DONE* when finished selecting\n"
        f"4️⃣ Provide your name and delivery address\n"
        f"5️⃣ Type *YES* to confirm your order ✅\n\n"
        f"📌 *OTHER COMMANDS*\n"
        f"• *MENU* — View all dishes & prices\n"
        f"• *HOURS* — Our opening times\n"
        f"• *ADDRESS* — Our location\n"
        f"• *DELIVERY* — Delivery fees & info\n"
        f"• *COMPLAINT* — Report an issue\n"
        f"• *HELP* — Show this message again\n\n"
        f"📞 Call us: {RESTAURANT_PHONE}\n"
        f"📍 {RESTAURANT_ADDRESS}"
    )

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_menu_text() -> str:
    """Format menu for WhatsApp"""
    text = f"🍽️ *{RESTAURANT_NAME} MENU*\n\n"
    current_cat = ""

    for num, item in sorted(MENU.items(), key=lambda x: x[1]['category']):
        if item['category'] != current_cat:
            current_cat = item['category']
            text += f"\n*{current_cat}*\n"
        text += f"{num}. {item['name']} - ₦{item['price']:,}\n"

    text += f"\n💡 Reply with numbers (e.g., '1, 3, 8')"
    text += f"\n🚚 Delivery: ₦{DELIVERY_FEE:,} (Free over ₦10,000)"
    return text

def format_cart(cart: list) -> str:
    """Format shopping cart"""
    if not cart:
        return "Empty"

    lines = []
    total = 0

    for i, num in enumerate(cart, 1):
        item = MENU[num]
        lines.append(f"{i}. {item['name']} - ₦{item['price']:,}")
        total += item['price']

    lines.append(f"\n*Subtotal: ₦{total:,}*")
    return '\n'.join(lines)

# ============================================
# MAIN MESSAGE HANDLER
# ============================================

def handle_message(incoming_msg: str, customer_phone: str) -> str:
    """Main entry point - processes all WhatsApp messages"""
    msg = incoming_msg.lower().strip()

    # Log incoming message
    log_message(customer_phone, 'incoming', incoming_msg)

    # Get customer info
    customer = get_customer_by_phone(customer_phone)
    customer_name = customer.get('name') if customer else None

    # Get conversation state
    state_raw = get_customer_state(customer_phone)
    state: Dict[str, Any] = json.loads(state_raw) if state_raw else {'step': 'idle'}

    # Route to appropriate handler
    if state.get('step') == 'ordering':
        reply = process_order(msg, customer_phone, state, customer_name)
    elif state.get('step') == 'reviewing':
        reply = process_review(msg, customer_phone, state)
    elif state.get('step') == 'confirming':
        reply = process_confirm(msg, customer_phone, state)
    elif state.get('step') == 'complaint':
        reply = process_complaint(msg, customer_phone, state, customer_name)
    elif state.get('step') == 'asking_name':
        reply = process_name(msg, customer_phone, state)
    elif state.get('step') == 'asking_address':
        reply = process_address(msg, customer_phone, state)
    else:
        reply = detect_intent(msg, customer_phone)

    # Log outgoing message
    log_message(customer_phone, 'outgoing', reply)

    return reply

# ============================================
# INTENT DETECTION
# ============================================

def detect_intent(msg: str, phone: str) -> str:
    """Figure out what customer wants"""

    # Greeting/Welcome intent — show instructions
    if any(w in msg for w in ['hi', 'hello', 'hey', 'start', 'hii', 'helo', 'hy', 'good morning', 'good afternoon', 'good evening']):
        return get_welcome_message()

    # Help intent — show instructions again
    if any(w in msg for w in ['help', 'instruction', 'how', 'guide', 'what can']):
        return get_welcome_message()

    # Order/Menu intent
    if any(w in msg for w in ['menu', 'order', 'food', 'hungry', 'rice', 'soup', 'eat', 'want', 'buy']):
        update_customer_state(phone, json.dumps({'step': 'ordering', 'cart': []}))
        return get_menu_text()

    # Complaint intent
    if any(w in msg for w in ['complaint', 'bad', 'problem', 'issue', 'wrong', 'cold', 'late', 'terrible']):
        update_customer_state(phone, json.dumps({'step': 'complaint'}))
        return "😔 We're sorry to hear that. Please describe what went wrong:\n\n(Type 'cancel' to go back)"

    # Booking intent
    if any(w in msg for w in ['book', 'table', 'reservation', 'seat']):
        return f"📅 To book a table, please call us at {RESTAURANT_PHONE}"

    # FAQ intents
    if any(w in msg for w in ['hour', 'open', 'close', 'time']):
        return f"🕐 *Opening Hours*\n{OPENING_HOURS}"

    if any(w in msg for w in ['location', 'address', 'where']):
        return f"📍 *Location*\n{RESTAURANT_ADDRESS}"

    if any(w in msg for w in ['phone', 'call', 'contact']):
        return f"📞 Call us: {RESTAURANT_PHONE}"

    if any(w in msg for w in ['delivery', 'deliver']):
        return f"🚚 We deliver!\nFee: ₦{DELIVERY_FEE:,}\nFREE delivery on orders over ₦10,000"

    if any(w in msg for w in ['human', 'manager', 'agent']):
        return f"👨‍💼 A manager will assist you. Please call {RESTAURANT_PHONE}"

    # AI Fallback — for anything else, try Groq AI first
    return get_ai_response(msg)

# ============================================
# CONVERSATION HANDLERS
# ============================================

def process_order(msg: str, phone: str, state: Dict, customer_name: Optional[str] = None) -> str:
    """Handle item selection"""
    if msg in ['cancel', 'back', 'stop']:
        update_customer_state(phone, json.dumps({'step': 'idle'}))
        return "Order cancelled. What else can I help you with?"

    cart = state.get('cart', [])
    added = []

    for part in msg.replace(',', ' ').split():
        num = part.strip()
        if num in MENU:
            cart.append(num)
            added.append(MENU[num]['name'])

    if not added:
        return "I didn't understand. Please send menu numbers like '1, 3, 5' or type 'menu' to see options."

    update_customer_state(phone, json.dumps({'step': 'reviewing', 'cart': cart, 'customer_name': customer_name}))

    return (f"✅ Added: {', '.join(added)}\n\n"
            f"*Your Cart:*\n{format_cart(cart)}\n\n"
            f"Reply:\n"
            f"• 'More' - add more items\n"
            f"• 'Done' - checkout\n"
            f"• 'Remove [number]' - remove item\n"
            f"• 'Cancel' - start over")

def process_review(msg: str, phone: str, state: Dict) -> str:
    """Handle cart review"""
    cart = state.get('cart', [])

    if msg in ['more', 'add', 'continue']:
        update_customer_state(phone, json.dumps({'step': 'ordering', 'cart': cart}))
        return get_menu_text() + f"\n\n*Current cart:*\n{format_cart(cart)}"

    if msg in ['done', 'checkout', 'ok', 'yes']:
        subtotal = sum(MENU[n]['price'] for n in cart)
        delivery = 0 if subtotal >= 10000 else DELIVERY_FEE
        total = subtotal + delivery

        update_customer_state(phone, json.dumps({
            'step': 'asking_name',
            'cart': cart,
            'subtotal': subtotal,
            'delivery': delivery,
            'total': total
        }))

        return "Please provide your name for the order:"

    if msg.startswith('remove'):
        try:
            idx = int(msg.split()[1]) - 1
            if 0 <= idx < len(cart):
                removed = cart.pop(idx)
                update_customer_state(phone, json.dumps({'step': 'reviewing', 'cart': cart}))
                return f"❌ Removed {MENU[removed]['name']}\n\n*Updated cart:*\n{format_cart(cart)}"
        except (IndexError, ValueError):
            pass
        return "To remove, reply 'remove 1' or 'remove 2'"

    if msg in ['cancel']:
        update_customer_state(phone, json.dumps({'step': 'idle'}))
        return "Order cancelled. What else can I help with?"

    return "Reply 'More' to add, 'Done' to checkout, or 'Cancel'"

def process_name(msg: str, phone: str, state: Dict) -> str:
    """Get customer name"""
    name = msg.strip()
    state['customer_name'] = name

    update_customer_state(phone, json.dumps({**state, 'step': 'asking_address'}))

    return f"Thanks {name}! Please provide your delivery address (or type 'pickup'):"

def process_address(msg: str, phone: str, state: Dict) -> str:
    """Get address and show final confirmation"""
    address = msg.strip()
    state['address'] = address if address.lower() != 'pickup' else 'Pickup at restaurant'

    cart = state.get('cart', [])
    total = state.get('total', 0)
    delivery = state.get('delivery', 0)
    customer_name = state.get('customer_name', 'Customer')

    update_customer_state(phone, json.dumps({**state, 'step': 'confirming'}))

    delivery_line = f"\nDelivery: ₦{delivery:,}" if delivery > 0 else "\n🎉 FREE delivery!"

    return (f"📋 *Order Summary*\n"
            f"Name: {customer_name}\n"
            f"Address: {state['address']}\n\n"
            f"{format_cart(cart)}"
            f"{delivery_line}\n"
            f"*TOTAL: ₦{total:,}*\n\n"
            f"Reply 'YES' to confirm or 'CANCEL' to cancel")

def process_confirm(msg: str, phone: str, state: Dict) -> str:
    """Final order confirmation"""
    cart = state.get('cart', [])

    if msg in ['yes', 'confirm', 'place', 'order', 'y']:
        items_text = ', '.join(MENU[n]['name'] for n in cart)
        total = state.get('total', 0)
        customer_name = state.get('customer_name')
        address = state.get('address', 'Pickup')

        order_id = save_order(phone, items_text, total, customer_name, address)
        update_customer_state(phone, json.dumps({'step': 'idle'}))

        # Generate Paystack payment link
        try:
            from payment import create_payment_link
            payment = create_payment_link(order_id, total, phone, customer_name)
        except Exception as e:
            print(f"Payment link error: {e}")
            payment = {"success": False}

        if payment.get("success"):
            return (
                f"✅ *Order #{order_id} Received!*\n\n"
                f"Name: {customer_name}\n"
                f"Items: {items_text}\n"
                f"Total: ₦{total:,}\n"
                f"Address: {address}\n\n"
                f"💳 *Pay now to confirm your order:*\n"
                f"{payment['link']}\n\n"
                f"⚠️ Your order will only be prepared after payment.\n"
                f"✅ You will get a WhatsApp message once payment is confirmed."
            )
        else:
            return (
                f"🎉 *Order #{order_id} CONFIRMED!*\n\n"
                f"Name: {customer_name}\n"
                f"Items: {items_text}\n"
                f"Total: ₦{total:,}\n"
                f"Address: {address}\n\n"
                f"⏰ Ready in: 25-30 minutes\n"
                f"📍 {RESTAURANT_ADDRESS}\n\n"
                f"Please pay on arrival/pickup."
            )

    if msg in ['add', 'more']:
        update_customer_state(phone, json.dumps({'step': 'ordering', 'cart': cart}))
        return get_menu_text()

    if msg in ['cancel', 'no', 'n']:
        update_customer_state(phone, json.dumps({'step': 'idle'}))
        return "Order cancelled. What else can I help with?"

    return "Reply 'YES' to confirm, 'ADD' for more, or 'CANCEL'"

def process_complaint(msg: str, phone: str, state: Dict, customer_name: Optional[str] = None) -> str:
    """Handle complaint"""
    if msg in ['cancel', 'back']:
        update_customer_state(phone, json.dumps({'step': 'idle'}))
        return "Complaint cancelled. How else can I help?"

    category = 'general'
    lowered = msg.lower()

    if any(w in lowered for w in ['food', 'cold', 'taste', 'salty', 'burnt']):
        category = 'food_quality'
    elif any(w in lowered for w in ['delivery', 'late', 'slow', 'driver']):
        category = 'delivery'
    elif any(w in lowered for w in ['staff', 'rude', 'service']):
        category = 'service'
    elif any(w in lowered for w in ['price', 'charge', 'billing']):
        category = 'billing'

    complaint_id = save_complaint(phone, category, msg, customer_name)
    update_customer_state(phone, json.dumps({'step': 'idle'}))

    return (f"📝 *Complaint #{complaint_id} LOGGED*\n\n"
            f"Category: {category.replace('_', ' ').title()}\n\n"
            f"We apologize. Our manager will contact you within 24 hours.\n\n"
            f"For urgent issues, call: {RESTAURANT_PHONE}")

def get_ai_response(msg: str) -> str:
    """Use Groq API via HTTP request"""
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mixtral-8x7b-32768",
                "messages": [
                    {
                        "role": "system",
                        "content": f"You are a helpful assistant for {RESTAURANT_NAME}. Keep replies short and friendly."
                    },
                    {"role": "user", "content": msg}
                ],
                "max_tokens": 150,
                "temperature": 0.7
            },
            timeout=10
        )

        data = response.json()
        return data['choices'][0]['message']['content']

    except Exception as e:
        print(f"Groq API error: {e}")
        return get_welcome_message()