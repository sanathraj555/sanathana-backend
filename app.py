from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_pymongo import PyMongo
from chatbot import chatbot_bp  # Add other blueprints like auth_bp if needed
import os

# === Initialize Flask App ===
app = Flask(__name__, static_folder="frontend/build", static_url_path="")

# === Enable CORS for frontend (allowed origin from Azure Static Web App) ===
CORS(app, resources={r"/*": {
    "origins": [os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")]
}}, supports_credentials=True)

# === MongoDB URI (from Azure environment variable ONLY) ===
mongo_uri = os.getenv("MONGO_URI")
if not mongo_uri:
    raise RuntimeError("❌ MONGO_URI environment variable not set in Azure App Service.")

app.config["MONGO_URI"] = mongo_uri

# === Initialize PyMongo ===
try:
    mongo = PyMongo(app)
    mongo.cx.admin.command("ping")
    print("✅ Connected to Azure Cosmos DB (MongoDB API)!")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    mongo = None

# === Global DB handle used by chatbot.py ===
app.mongo_chatbot = mongo.cx.get_database("sanathana_chatbot_v1") if mongo else None

# === Register Blueprints ===
app.register_blueprint(chatbot_bp, url_prefix="/chatbot")
# app.register_blueprint(auth_bp, url_prefix="/auth")  # Optional

# === Serve Static Frontend Assets ===
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(app.static_folder, 'static'), filename)

# === React SPA Fallback for Non-API Routes ===
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react_app(path):
    if path.startswith(("auth", "chatbot", "api")):
        return jsonify({"error": "API route not found"}), 404
    return send_from_directory(app.static_folder, "index.html")

# === Run Server (Azure provides PORT env var) ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
