import os
import requests
from flask import Flask, request
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

tf = TimezoneFinder()

def get_ai_response(user_message):
    """Get response from OpenRouter AI (free)"""
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "microsoft/phi-3-mini-128k-instruct:free",
            "messages": [
                {"role": "system", "content": "You are J.A.R.V.I.S., a helpful AI assistant created by @Introspection007. Be friendly, warm, and answer questions directly. Keep responses short and natural (1-2 sentences)."},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 150
        }
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        return None
    except Exception as e:
        print(f"AI error: {e}")
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
            temp = round(data["main"]["temp"])
            feels_like = round(data["main"]["feels_like"])
            humidity = data["main"]["humidity"]
            description = data["weather"][0]["description"].capitalize()
            wind_speed = data["wind"]["speed"]
            city_name = data["name"]
            
            return {
                "city": city_name,
                "temp": temp,
                "feels_like": feels_like,
                "humidity": humidity,
                "description": description,
                "wind": wind_speed
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

I'm your personal AI assistant!

**Commands:**
/start - Show menu
/help - All commands
/time - Current time
/time [city] - Time in any city
/weather [city] - Get weather

**Just type anything and I'll respond!**

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/help":
            reply = """🔷 **J.A.R.V.I.S. Commands** 🔷

/time - Current time (India)
/time London - Time in London
/weather London - Weather in London
/start - Show menu

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text.startswith("/time"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                time_data = get_local_time(parts[1])
                reply = f"🕐 **Time in {time_data['city']}:** {time_data['time']}\n📅 **Date:** {time_data['date']}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
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
            # Get AI response
            ai_response = get_ai_response(text)
            if ai_response:
                reply = f"🤖 {ai_response}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            else:
                # Simple fallback responses
                msg_lower = text.lower()
                if "hello" in msg_lower or "hi" in msg_lower:
                    reply = f"🤖 Hello! How can I help you today?\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                elif "time" in msg_lower:
                    time_data = get_local_time()
                    reply = f"🕐 It's {time_data['time']} in {time_data['city']}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                elif "weather" in msg_lower:
                    reply = f"🌤️ Use /weather [city] to get weather!\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                elif "thank" in msg_lower:
                    reply = f"🤖 You're welcome! 😊\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                else:
                    reply = f"🤖 I'm J.A.R.V.I.S.! Use /weather [city] for weather, /time for time, or just ask me anything!\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
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
