import os
import requests
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENWEATHER_API_KEY = "6d41f0ecd281e84165a9b8cf76821a17"

def get_groq_response(user_message):
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama3-70b-8192",
            "messages": [
                {"role": "system", "content": "You are J.A.R.V.I.S., a helpful AI assistant created by @Introspection007. Be friendly and concise."},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 200
        }
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        return None
    except:
        return None

def get_weather(city):
    """Get weather from OpenWeatherMap API"""
    try:
        # First, get coordinates for the city
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_response = requests.get(geo_url, timeout=5)
        
        if geo_response.status_code == 200 and geo_response.json():
            lat = geo_response.json()[0]["lat"]
            lon = geo_response.json()[0]["lon"]
            city_name = geo_response.json()[0]["name"]
            
            # Get weather data
            weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
            weather_response = requests.get(weather_url, timeout=5)
            
            if weather_response.status_code == 200:
                data = weather_response.json()
                temp = round(data["main"]["temp"])
                feels_like = round(data["main"]["feels_like"])
                humidity = data["main"]["humidity"]
                description = data["weather"][0]["description"].capitalize()
                wind_speed = data["wind"]["speed"]
                
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

I'm your AI assistant powered by Groq!

**Commands:**
/start - Show menu
/help - All commands
/time - Current time
/weather [city] - Get accurate weather

**Just type anything and I'll respond!**

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/help":
            reply = """🔷 **J.A.R.V.I.S. Commands** 🔷

/time - Current time
/weather [city] - Get weather (e.g., /weather London)
/start - Show menu

━━━━━━━━━━━━━━━━━━━━━
🤖 **Powered By @Introspection007**"""
        
        elif text == "/time":
            now = datetime.now()
            reply = f"🕐 **Time:** {now.strftime('%I:%M %p')}\n📅 **Date:** {now.strftime('%A, %B %d, %Y')}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
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
            ai_response = get_groq_response(text)
            if ai_response:
                reply = f"🤖 {ai_response}\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
            else:
                reply = f"Sorry, I'm having trouble. Please try again.\n\n━━━━━━━━━━━━━━━━━━━━━\n🤖 **Powered By @Introspection007**"
        
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
