import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import redis

app = Flask(__name__, static_folder="static")
CORS(app)

# Подключение к Redis (Render обычно предоставляет REDIS_URL в env)
redis_url = os.getenv("REDIS_URL", "redis://red-d2m4543uibrs73fqt7c0:6379")
redis_client = redis.from_url(redis_url)

PRODUCTS_KEY = "products"
ORDERS_KEY = "orders"
ADMINS = {1286638668}  # <- поставь сюда свой реальный Telegram ID (числом)

# Отдача фронтенда
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index_flask.html")

# Хелперы для Redis
def get_all_products():
    products_json = redis_client.lrange(PRODUCTS_KEY, 0, -1)
    return [json.loads(p) for p in products_json]

def save_product(product_data):
    products = get_all_products()
    new_id = max([p["id"] for p in products], default=0) + 1 if products else 1
    product_data["id"] = new_id
    redis_client.rpush(PRODUCTS_KEY, json.dumps(product_data))
    return product_data

def get_orders_for_user(user_id):
    orders_json = redis_client.lrange(ORDERS_KEY, 0, -1)
    orders = [json.loads(o) for o in orders_json]
    return [o for o in orders if o.get("user_id") == user_id]

def save_order(order_data):
    orders = redis_client.lrange(ORDERS_KEY, 0, -1)
    new_id = max([json.loads(o)["id"] for o in orders], default=0) + 1 if orders else 1
    order_data["id"] = new_id
    redis_client.rpush(ORDERS_KEY, json.dumps(order_data))
    return order_data

# API
@app.route("/api/products", methods=["GET"])
def api_get_products():
    return jsonify(get_all_products())

@app.route("/api/products", methods=["POST"])
def api_add_product():
    data = request.json
    product = save_product(data)
    return jsonify({"success": True, "product": product})

@app.route("/api/orders", methods=["POST"])
def api_create_order():
    data = request.json
    order = {
        "user_id": data.get("userId"),
        "items": data.get("items"),
        "total": data.get("total"),
        "status": data.get("status", "pending")
    }
    saved = save_order(order)
    return jsonify({"success": True, "order": saved})

@app.route("/api/orders/<int:user_id>", methods=["GET"])
def api_get_orders(user_id):
    return jsonify(get_orders_for_user(user_id))





# Инициализация с тестовыми товарами
def init_sample_data():
    if not get_all_products():
        sample = [
            {"name": "Жидкость Mango", "category": "liquids", "price": 450, "stock": 10, "description": "Вкусный манго", "emoji": "🥭"},
            {"name": "Картридж JUUL", "category": "cartridges", "price": 300, "stock": 20, "description": "Оригинальные картриджи", "emoji": "💨"},
            {"name": "Под RELX Mint", "category": "pods", "price": 280, "stock": 12, "description": "Мятный вкус", "emoji": "🔥"},
            {"name": "Vaporesso XROS 3", "category": "devices", "price": 2800, "stock": 5, "description": "Компактная POD-система", "emoji": "⚡"},
        ]
        for p in sample:
            save_product(p)

if __name__ == "__main__":
    init_sample_data()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
