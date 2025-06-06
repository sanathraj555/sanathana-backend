from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
import os
import logging
from dotenv import load_dotenv

# === Import Blueprints ===
from chatbot import chatbot_bp
from auth import auth_bp

# === Load environment variables from .env ===
load_dotenv()

# === Initialize Flask App ===
app = Flask(__name__, static_folder="frontend/build", static_url_path="")

# === Enable CORS (Frontend origin from Azure Static Web App) ===
CORS(app, resources={r"/*": {
    "origins": [os.getenv("FRONTEND_ORIGIN", "https://yellow-hill-0dae7d700.6.azurestaticapps.net")]
}}, supports_credentials=True)

# === MongoDB URI from Environment Variable ===
mongo_uri = os.getenv("MONGO_URI")
if not mongo_uri:
    raise RuntimeError("❌ MONGO_URI environment variable is missing. Set it in Azure App Service → Configuration.")

# === MongoDB Setup (local or Azure CosmosDB) ===
try:
    client = MongoClient(mongo_uri)
    client.admin.command("ping")     # Test connection
    db = client.get_database("sanathana_chatbot_v1")
    app.mongo_chatbot = db
    app.logger.info("✅ Connected to MongoDB: sanathana_chatbot_v1")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    app.mongo_chatbot = None

# === Register Blueprints ===
app.register_blueprint(chatbot_bp, url_prefix="/chatbot")
app.register_blueprint(auth_bp, url_prefix="/auth")

# === Health Check Route ===
@app.route('/health', methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200

# === Serve Static Files (React build) ===
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(app.static_folder, "static"), filename)

# === Catch-all for SPA routes (React frontend) ===
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react_app(path):
    # Prevent intercepting API routes
    if path.startswith(("auth", "chatbot", "api")):
        return jsonify({"error": "API route not found"}), 404
    return send_from_directory(app.static_folder, "index.html")

# === Run Server ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
