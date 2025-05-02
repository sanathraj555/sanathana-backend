from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_pymongo import PyMongo
import os
import logging

# ✅ Initialize Flask App
app = Flask(__name__, static_folder='frontend/build', static_url_path='')

# ✅ Logging setup
logging.basicConfig(level=logging.INFO)

# ✅ CORS Setup
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "https://yellow-hill-0dae7d700.6.azurestaticapps.net"
        ]
    }
}, supports_credentials=True, methods=["GET", "POST", "OPTIONS"])

# ✅ Cosmos MongoDB Connection (vCore or API for MongoDB)
cosmos_uri = os.getenv(
    'MONGO_URI',
    'mongodb://sanathana-mongodb:m1ErbvRoj8vA4M3tD56mvNTEch5tasOIP0mrvfxBtqiTZYNdEVz172UeCa5qK1YI5J8xZSItPwYNACDbmUcvzw==@sanathana-mongodb.mongo.cosmos.azure.com:10255/?ssl=true&retrywrites=false&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@sanathana-mongodb@'
)

# ✅ Flask config for PyMongo
app.config["MONGO_URI"] = cosmos_uri

# ✅ Mongo Client Initialization
try:
    mongo = PyMongo(app)
    mongo.cx.admin.command('ping')
    app.logger.info("✅ Connected to Azure Cosmos DB (MongoDB API)!")
    mongo_chatbot = mongo.cx.get_database("sanathana_chatbot_v1")
except Exception as e:
    app.logger.error(f"❌ Cosmos DB Connection Failed: {e}")
    mongo = None
    mongo_chatbot = None

# ✅ Import & Register Blueprints
from auth import auth_bp
from chatbot import chatbot_bp

app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(chatbot_bp, url_prefix="/chatbot")

# ✅ Serve static frontend files
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(app.static_folder, 'static'), filename)

# ✅ Catch-all route for React SPA routing
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react_app(path):
    if path.startswith("auth") or path.startswith("chatbot") or path.startswith("api"):
        return jsonify({"error": "API route not found"}), 404
    return send_from_directory(app.static_folder, 'index.html')

# ✅ Health Check Route
@app.route('/health', methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200

# ✅ Start Flask App
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
