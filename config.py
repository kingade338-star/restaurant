import os
from dotenv import load_dotenv

load_dotenv()

# Twilio
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

# Groq
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Admin
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'iyameta2024')

#paystack
PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY')

# Validate
if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, GROQ_API_KEY]):
    print("⚠️ Warning: Some environment variables are missing. Check your .env file.")