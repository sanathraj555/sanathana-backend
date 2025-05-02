from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_pymongo import PyMongo
import os
import logging

# ✅ Initialize Flask App
app = Flask(__name__, static_folder='frontend/build', static_url_path='')

# ✅ Allow CORS for frontend requests
CORS(app, resources={r"/*": {"origins": ["https://yellow-hill-0dae7d700.6.azurestaticapps.net"]}}, supports_credentials=True, methods=["GET","POST","OPTIONS"])

# ✅ Azure Cosmos DB URI (MongoDB API) using environment variable
cosmos_uri = os.getenv('MONGO_URI','mongodb+srv://sars:Sanathana123@sanathanadb.mongo.cosmos.azure.com/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000')  # Fallback to default if env var not set

# ✅ Configure MongoDB in Flask
app.config["MONGO_URI"] = cosmos_uri

# ✅ Initialize PyMongo Client
try:
    mongo = PyMongo(app)
    mongo.cx.admin.command('ping')  # Ping Cosmos DB
    app.logger.info("✅ Connected to Azure Cosmos DB (MongoDB API)!")  # Ensure DB connection is successful
except Exception as e:
    app.logger.error(f"❌ Cosmos DB Connection Failed: {e}")
    mongo = None

# ✅ Get the Correct Database Instance
if mongo:
    mongo_chatbot = mongo.cx.get_database("sanathana_chatbot_v1")
else:
    mongo_chatbot = None

# ✅ Register Blueprints (APIs)
from auth import auth_bp
from chatbot import chatbot_bp

app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(chatbot_bp, url_prefix="/chatbot")

# ✅ Serve static files (like JS, CSS, Images) from React build
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(app.static_folder, 'static'), filename)

# ✅ Serve React frontend (index.html) for all other non-API routes
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react_app(path):
    if path.startswith("auth") or path.startswith("chatbot") or path.startswith("api"):
        return jsonify({"error": "API route not found"}), 404
    return send_from_directory(app.static_folder, 'index.html')

# ✅ Health check endpoint for monitoring
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

# ✅ Run Flask Server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Dynamic port for Azure
    app.run(host="0.0.0.0", port=port, debug=False)  # Don't run in debug mode in production
