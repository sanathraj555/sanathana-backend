from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_pymongo import PyMongo
from auth import auth_bp
from chatbot import chatbot_bp
import os

# ✅ Initialize Flask App
app = Flask(__name__, static_folder='frontend/build', static_url_path='')

# ✅ Allow CORS for frontend requests
CORS(app, resources={r"/*": {"origins": ["https://yellow-hill-0dae7d700.6.azurestaticapps.net"]}}, supports_credentials=True)

# ✅ Azure Cosmos DB URI (MongoDB API)
cosmos_uri = "mongodb+srv://sars:Sanathana123@sanathanadb.mongo.cosmos.azure.com/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"

# ✅ Configure MongoDB in Flask
app.config["MONGO_URI"] = cosmos_uri

# ✅ Initialize PyMongo Client
try:
    mongo = PyMongo(app)
    mongo.cx.admin.command('ping')  # Ping Cosmos DB
    print("✅ Connected to Azure Cosmos DB (MongoDB API)!")
except Exception as e:
    print(f"❌ Cosmos DB Connection Failed: {e}")
    mongo = None

# ✅ Get the Correct Database Instance
if mongo:
    mongo_chatbot = mongo.cx.get_database("sanathana_chatbot_v1")
else:
    mongo_chatbot = None

# ✅ Register Blueprints (APIs)
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
    # Important: Only fallback for non-API routes
    if path.startswith("auth") or path.startswith("chatbot") or path.startswith("api"):
        return jsonify({"error": "API route not found"}), 404
    return send_from_directory(app.static_folder, 'index.html')

# ✅ Run Flask Server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Dynamic port for Azure
    app.run(host="0.0.0.0", port=port, debug=False)
