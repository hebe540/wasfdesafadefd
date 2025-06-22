import os
import json
from flask import Flask, redirect, url_for, request, session, render_template
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:5000/callback")
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

API_BASE_URL = "https://discord.com/api"
OAUTH_SCOPE = "identify guilds"

CONFIG_PATH = "guild_config.json"
if not os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "w") as f:
        json.dump({}, f)

def get_guild_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_guild_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)

def get_user_guilds(token_type, token):
    url = f"{API_BASE_URL}/users/@me/guilds"
    headers = {"Authorization": f"{token_type} {token}"}
    r = requests.get(url, headers=headers)
    return r.json()

def get_bot_guilds():
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    r = requests.get(f"{API_BASE_URL}/users/@me/guilds", headers=headers)
    return r.json()

@app.route("/")
def index():
    if "token" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/login")
def login():
    return redirect(
        f"{API_BASE_URL}/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope={OAUTH_SCOPE}"
    )

@app.route("/callback")
def callback():
    code = request.args.get("code")
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": OAUTH_SCOPE,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post(f"{API_BASE_URL}/oauth2/token", data=data, headers=headers)
    print("OAuth Response:", r.text)
    token_data = r.json()
    if "access_token" not in token_data:
        return f"OAuth failed: {token_data}", 400
    session["token"] = token_data
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    if "token" not in session:
        return redirect(url_for("login"))

    token = session["token"]
    try:
        user_guilds = get_user_guilds(token["token_type"], token["access_token"])
    except (KeyError, TypeError):
        return redirect(url_for("logout"))

    bot_guilds = get_bot_guilds()
    bot_guild_ids = {g['id'] for g in bot_guilds}

    mutual_guilds = [g for g in user_guilds if g['id'] in bot_guild_ids and g['permissions'] & 0x8]
    session["admin_guild_ids"] = [g['id'] for g in mutual_guilds]
    return render_template("dashboard.html", guilds=mutual_guilds)

@app.route("/dashboard/<guild_id>")
def manage_guild(guild_id):
    config = get_guild_config()
    settings = config.get(guild_id, {"prefix": "!", "log_channel": None})
    is_admin = guild_id in session.get("admin_guild_ids", [])
    return render_template("server.html", guild_id=guild_id, settings=settings, is_admin=is_admin)

@app.route("/dashboard/<guild_id>/update", methods=["POST"])
def update_guild(guild_id):
    if guild_id not in session.get("admin_guild_ids", []):
        return "Unauthorized", 403

    config = get_guild_config()
    prefix = request.form.get("prefix")
    log_channel = request.form.get("log_channel")
    config[guild_id] = {
        "prefix": prefix,
        "log_channel": log_channel
    }
    save_guild_config(config)
    return redirect(url_for("manage_guild", guild_id=guild_id))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
