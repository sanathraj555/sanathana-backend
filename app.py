from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
import os
import logging
from dotenv import load_dotenv

# === Load environment variables from .env ===
load_dotenv()

# === Initialize Flask App ===
app = Flask(__name__, static_folder='frontend/build', static_url_path='')

# === Logging Setup ===
logging.basicConfig(level=logging.INFO)

# === CORS Configuration ===
CORS(app, supports_credentials=True, origins=[
    "http://localhost:3000",
    "https://yellow-hill-0dae7d700.6.azurestaticapps.net"
])

# === MongoDB Setup (local or Azure CosmosDB) ===
# === MongoDB Setup (local or Azure CosmosDB) ===
mongo_uri = os.getenv('MONGO_URI')

try:
    client = MongoClient(mongo_uri)  # ✅ No TLS params for local
    client.admin.command("ping")     # Test connection
    app.mongo_chatbot = client["sanathana_chatbot_v1"]
    app.logger.info("✅ Connected to MongoDB: sanathana_chatbot_v1")
except Exception as e:
    app.logger.error(f"❌ MongoDB connection failed: {e}")
    app.mongo_chatbot = None

# === Register Blueprints ===
from auth import auth_bp
from chatbot import chatbot_bp

app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(chatbot_bp, url_prefix="/chatbot")

# === Health Check Route ===
@app.route('/health', methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200

# === Serve Static Files (React build) ===
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(app.static_folder, 'static'), filename)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react_app(path):
    # Prevent intercepting API routes
    if path.startswith(("auth", "chatbot", "api")):
        return jsonify({"error": "API route not found"}), 404
    return send_from_directory(app.static_folder, 'index.html')

# === Run Server ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
