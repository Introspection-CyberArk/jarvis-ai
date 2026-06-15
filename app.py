import os
import requests
from flask import Flask, request
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

tf = TimezoneFinder()

def get_user_timezone(city=None):
    """Get timezone from city name"""
    if not city:
        return "Asia/Kolkata"  # Default to IST
    
    try:
        # Get coordinates for city
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
        response = requests.get(geo_url, timeout=5)
        
        if response.status_code == 200 and response.json():
            lat = response.json()[0]["lat"]
            lon = response.json()[0]["lon"]
            timezone = tf.timezone_at(lat=lat, lng=lon)
            if timezone:
                return timezone
        return "Asia/Kolkata"
    except:
        return "Asia/Kolkata"

def get_groq_response(user_message):
    """Get response from Groq AI"""
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "mixtral-8x7b-32768",
            "messages": [
                {"role": "system", "content": "You are J.A.R.V.I.S., a helpful AI assistant created by @Introspection007. Be friendly, warm, and answer questions directly. Keep responses short and natural."},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 200
        }
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        return None
    except Exception as e:
        print(f"Groq error: {e}")
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
                "wind": wind_speed,
                "lat": data["coord"]["lat"],
                "lon": data["coord"]["lon"]
            }
        return None
    except Exception as e:
        print(f"Weather error: {e}")
        return None

def get_local_time(city=None):
    """Get local time for a city"""
    try:
        if city:
            # Get coordinates and timezone for city
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
                        "date": now.strftime('%A, %B %d, %Y'),
                        "timezone": timezone_str
                    }
        
        # Default to IST (India)
        tz = pytz.timezone("Asia/Kolkata")
        now = datetime.now(tz)
        return {
            "city": "India",
            "time": now.strftime('%I:%M %p'),
            "date": now.strftime('%A, %B %d, %Y'),
            "timezone": "Asia/Kolkata"
        }
    except Exception as e:
        print(f"Time error: {e}")
        tz = pytz.timezone("Asia/Kolkata")
        now = datetime.now(tz)
        return {
            "city": "India",
            "time": now.strftime('%I:%M %p'),
            "date": now.strftime('%A, %B %d, %Y'),
            "timezone": "Asia/Kolkata"
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
                # Time for specific city
                city = parts[1]
                time_data = get_local_time(city)
                if time_data:
                    reply = f"🕐 **Time in {time_data['city']}:** {time_data['time']}\n📅 **Date:** {time_data['date']}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
                else:
                    reply = f"🕐 Couldn't find time for '{city}'.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            else:
                # Default time
                time_data = get_local_time()
                reply = f"🕐 **Time:** {time_data['time']}\n📅 **Date:** {time_data['date']}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
        elif text.startswith("/weather"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                reply = "🌤️ Please specify a city.\n\nExample: `/weather London`\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            else:
                city = parts[1]
                weather = get_weather(city)
                if weather:
                    reply = f"""🌤️ **Weather in {weather['city']}**

🌡️ Temperature: {weather['temp']}°C (feels like {weather['feels_like']}°C)
☁️ Conditions: {weather['description']}
💧 Humidity: {weather['humidity']}%
💨 Wind Speed: {weather['wind']} m/s

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
                else:
                    reply = f"🌤️ Couldn't find weather for '{city}'. Please check the city name.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"""
        
        else:
            # Get AI response for any question
            ai_response = get_groq_response(text)
            if ai_response:
                reply = f"🤖 {ai_response}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            else:
                # Fallback response
                reply = f"I'm J.A.R.V.I.S.! Ask me for weather, time, or any question.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
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
