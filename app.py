import os
import requests
from flask import Flask, request
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder
import random

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

tf = TimezoneFinder()

# Debug: Print API key status on startup
print(f"OpenRouter API Key present: {bool(OPENROUTER_API_KEY)}")
print(f"OpenWeather API Key present: {bool(OPENWEATHER_API_KEY)}")

def get_ai_response(user_message):
    """Get response from OpenRouter AI"""
    if not OPENROUTER_API_KEY:
        print("No OpenRouter API key found!")
        return None
    
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://t.me/Jarvs_Ai_bot",
            "X-Title": "J.A.R.V.I.S. Bot"
        }
        payload = {
            "model": "nousresearch/hermes-3-llama-3.1-405b:free",
            "messages": [
                {"role": "system", "content": "You are J.A.R.V.I.S., a helpful AI assistant. Be friendly, conversational, and answer questions naturally. Keep responses concise but helpful."},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.8,
            "max_tokens": 250
        }
        
        print(f"Sending request to OpenRouter for: {user_message[:50]}...")
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        
        print(f"OpenRouter response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            reply = result["choices"][0]["message"]["content"]
            print(f"Got response: {reply[:100]}...")
            return reply
        else:
            print(f"OpenRouter error: {response.status_code} - {response.text[:200]}")
            return None
            
    except requests.exceptions.Timeout:
        print("OpenRouter timeout")
        return None
    except Exception as e:
        print(f"OpenRouter exception: {e}")
        return None

def get_weather(city):
    """Get weather from OpenWeatherMap API"""
    if not OPENWEATHER_API_KEY:
        return None
    
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
        response = requests.get(url, timeout=8)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "city": data["name"],
                "temp": round(data["main"]["temp"]),
                "feels_like": round(data["main"]["feels_like"]),
                "humidity": data["main"]["humidity"],
                "description": data["weather"][0]["description"].capitalize(),
                "wind": data["wind"]["speed"]
            }
        return None
    except Exception as e:
        print(f"Weather error: {e}")
        return None

def get_local_time(city=None):
    """Get local time for a city"""
    try:
        if city:
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
            response = requests.get(geo_url, timeout=5)
            
            if response.status_code == 200 and response.json():
                lat = response.json()[0]["lat"]
                lon = response.json()[0]["lon"]
                timezone_str = tf.timezone_at(lat=lat, lng=lon)
                city_name = response.json()[0]["name"]
                
                if timezone_str:
                    tz = pytz.timezone(timezone_str)
                    now = datetime.now(tz)
                    return {
                        "city": city_name,
                        "time": now.strftime('%I:%M %p'),
                        "date": now.strftime('%A, %B %d, %Y')
                    }
        
        tz = pytz.timezone("Asia/Kolkata")
        now = datetime.now(tz)
        return {
            "city": "India",
            "time": now.strftime('%I:%M %p'),
            "date": now.strftime('%A, %B %d, %Y')
        }
    except:
        tz = pytz.timezone("Asia/Kolkata")
        now = datetime.now(tz)
        return {
            "city": "India",
            "time": now.strftime('%I:%M %p'),
            "date": now.strftime('%A, %B %d, %Y')
        }

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        
        if not chat_id or not text:
            return "", 200
        
        # Send typing indicator
        try:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendChatAction", 
                         json={"chat_id": chat_id, "action": "typing"}, timeout=2)
        except:
            pass
        
        # Handle commands
        if text == "/start":
            reply = """🔷 **J.A.R.V.I.S. Online** 🔷

I'm your personal AI assistant - just like ChatGPT!

**Commands:**
/start - Show menu
/help - All commands
/time - Current time
/time [city] - Time in any city
/weather [city] - Get weather

**Just type anything - I'll chat with you naturally!**

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/help":
            reply = """🔷 **J.A.R.V.I.S. Commands** 🔷

/time - Current time (India)
/time London - Time in London
/weather London - Weather in London
/start - Show menu

**Or just chat with me naturally!**

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text.startswith("/time"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                time_data = get_local_time(parts[1])
                if time_data:
                    reply = f"🕐 **Time in {time_data['city']}:** {time_data['time']}\n📅 **Date:** {time_data['date']}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                else:
                    reply = f"🕐 Couldn't find time for '{parts[1]}'.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            else:
                time_data = get_local_time()
                reply = f"🕐 **Time:** {time_data['time']}\n📅 **Date:** {time_data['date']}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        elif text.startswith("/weather"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                reply = "🌤️ Please specify a city.\n\nExample: `/weather London`\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            else:
                weather = get_weather(parts[1])
                if weather:
                    reply = f"""🌤️ **Weather in {weather['city']}**

🌡️ Temperature: {weather['temp']}°C (feels like {weather['feels_like']}°C)
☁️ Conditions: {weather['description']}
💧 Humidity: {weather['humidity']}%
💨 Wind Speed: {weather['wind']} m/s

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
                else:
                    reply = f"🌤️ Couldn't find weather for '{parts[1]}'.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"""
        
        else:
            # Get AI response for ANY message
            ai_response = get_ai_response(text)
            
            if ai_response:
                reply = f"🤖 {ai_response}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            else:
                # Fallback response when AI fails
                reply = f"🤖 I'm having trouble connecting to my AI service. Please try again in a moment.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
        
        return "", 200
        
    except Exception as e:
        print(f"Error: {e}")
        return "", 200

@app.route("/", methods=["GET"])
def index():
    return {"status": "J.A.R.V.I.S. is running!", "creator": "@Introspection007"}

if __name__ == "__main__":
    app.run()
