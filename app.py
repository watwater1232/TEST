import os
import json
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import redis

app = Flask(__name__, static_folder="static")
CORS(app)

# Redis connection
redis_url = os.getenv("REDIS_URL", "redis://red-d2m4543uibrs73fqt7c0:6379")
try:
    redis_client = redis.from_url(redis_url, decode_responses=True)
    redis_client.ping()
    print("✅ Connected to Redis")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
    exit(1)

# Redis keys
PRODUCTS_KEY = "vape_shop:products"
ORDERS_KEY = "vape_shop:orders"
USERS_KEY = "vape_shop:users"
PROMOS_KEY = "vape_shop:promos"
STATS_KEY = "vape_shop:stats"

# Admin Telegram IDs
ADMIN_IDS = {1286638668, 580981359}

# Helpers
def get_current_time():
    return datetime.now().isoformat()

def get_next_id(key_prefix):
    counter_key = f"{key_prefix}:counter"
    return redis_client.incr(counter_key)

# ================== PRODUCTS ==================
def get_all_products():
    try:
        product_keys = redis_client.keys(f"{PRODUCTS_KEY}:*")
        products = []
        for key in product_keys:
            if key.endswith(":counter"):
                continue
            data = redis_client.hgetall(key)
            if data:
                try:
                    data["id"] = int(data["id"])
                    data["price"] = int(data["price"])
                    data["stock"] = int(data["stock"])
                except:
                    continue
                products.append(data)
        return sorted(products, key=lambda x: x["id"])
    except Exception as e:
        print(f"Error get_all_products: {e}")
        return []

def save_product(product_data):
    try:
        if "id" not in product_data:
            product_data["id"] = get_next_id(PRODUCTS_KEY)
        key = f"{PRODUCTS_KEY}:{product_data['id']}"
        product_data.setdefault("created_at", get_current_time())
        product_data["updated_at"] = get_current_time()
        redis_client.hset(key, mapping=product_data)
        return product_data
    except Exception as e:
        print(f"Error save_product: {e}")
        return None

def delete_product(product_id):
    try:
        key = f"{PRODUCTS_KEY}:{product_id}"
        return redis_client.delete(key) > 0
    except Exception as e:
        print(f"Error delete_product: {e}")
        return False

# ================== ORDERS ==================
def get_all_orders():
    try:
        keys = redis_client.keys(f"{ORDERS_KEY}:*")
        orders = []
        for key in keys:
            if key.endswith(":counter"):
                continue
            data = redis_client.hgetall(key)
            if data:
                try:
                    data["id"] = int(data["id"])
                    data["userId"] = int(data["userId"])
                    data["total"] = int(data["total"])
                    try:
                        data["items"] = json.loads(data.get("items", "[]"))
                    except:
                        data["items"] = []
                except:
                    continue
                orders.append(data)
        return sorted(orders, key=lambda x: x["id"], reverse=True)
    except Exception as e:
        print(f"Error get_all_orders: {e}")
        return []

def save_order(order_data):
    try:
        if "id" not in order_data:
            order_data["id"] = get_next_id(ORDERS_KEY)

        key = f"{ORDERS_KEY}:{order_data['id']}"
        order_data.setdefault("created_at", get_current_time())
        order_data.setdefault("status", "pending")

        # save items
        items = order_data.pop("items", [])
        order_data["items"] = json.dumps(items)
        redis_client.hset(key, mapping=order_data)

        # return items back
        order_data["items"] = items

        # 🔥 decrease stock
        for item in items:
            product_key = f"{PRODUCTS_KEY}:{item['id']}"
            if redis_client.exists(product_key):
                try:
                    current_stock = int(redis_client.hget(product_key, "stock") or 0)
                except:
                    current_stock = 0
                new_stock = max(0, current_stock - int(item["quantity"]))
                redis_client.hset(product_key, "stock", new_stock)

        update_stats()
        return order_data
    except Exception as e:
        print(f"Error save_order: {e}")
        return None

def get_orders_by_user(user_id):
    try:
        return [o for o in get_all_orders() if o["userId"] == user_id]
    except Exception as e:
        print(f"Error get_orders_by_user: {e}")
        return []

# ================== USERS ==================
def get_user(user_id):
    try:
        key = f"{USERS_KEY}:{user_id}"
        data = redis_client.hgetall(key)
        if data:
            data["id"] = int(data["id"])
            data["bonus"] = int(data.get("bonus", 0))
            data["referrals"] = json.loads(data.get("referrals", "[]"))
            data["isAdmin"] = user_id in ADMIN_IDS
        return data
    except Exception as e:
        print(f"Error get_user: {e}")
        return None

def save_user(user_data):
    try:
        key = f"{USERS_KEY}:{user_data['id']}"
        referrals = user_data.get("referrals", [])
        user_data["referrals"] = json.dumps(referrals)
        user_data.setdefault("created_at", get_current_time())
        user_data["updated_at"] = get_current_time()
        redis_client.hset(key, mapping=user_data)
        user_data["referrals"] = referrals
        return user_data
    except Exception as e:
        print(f"Error save_user: {e}")
        return None

# ================== PROMOS ==================
def get_all_promos():
    try:
        keys = redis_client.keys(f"{PROMOS_KEY}:*")
        promos = []
        for key in keys:
            data = redis_client.hgetall(key)
            if data:
                try:
                    data["discount"] = int(data["discount"])
                    data["uses"] = int(data["uses"])
                    data["used"] = int(data.get("used", 0))
                except:
                    continue
                promos.append(data)
        return promos
    except Exception as e:
        print(f"Error get_all_promos: {e}")
        return []

def save_promo(promo_data):
    try:
        key = f"{PROMOS_KEY}:{promo_data['code']}"
        promo_data.setdefault("used", 0)
        promo_data.setdefault("created_at", get_current_time())
        promo_data["updated_at"] = get_current_time()
        redis_client.hset(key, mapping=promo_data)
        return promo_data
    except Exception as e:
        print(f"Error save_promo: {e}")
        return None

# ================== STATS ==================
def update_stats():
    try:
        stats = {
            "total_orders": len(get_all_orders()),
            "total_products": len(get_all_products()),
            "total_users": len(redis_client.keys(f"{USERS_KEY}:*")),
            "total_revenue": sum(o["total"] for o in get_all_orders() if o["status"] == "completed"),
            "updated_at": get_current_time()
        }
        redis_client.hset(STATS_KEY, mapping=stats)
        return stats
    except Exception as e:
        print(f"Error update_stats: {e}")
        return {}

def get_stats():
    try:
        stats = redis_client.hgetall(STATS_KEY)
        if stats:
            for k in ["total_orders", "total_products", "total_users", "total_revenue"]:
                stats[k] = int(stats.get(k, 0))
        return stats or update_stats()
    except Exception as e:
        print(f"Error get_stats: {e}")
        return update_stats()

# ================== ROUTES ==================
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index_flask.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)

# API PRODUCTS
@app.route("/api/products", methods=["GET"])
def api_get_products():
    return jsonify(get_all_products())

@app.route("/api/products", methods=["POST"])
def api_add_product():
    data = request.json
    product = save_product(data)
    return jsonify({"success": True, "product": product})

@app.route("/api/products/<int:pid>", methods=["PUT"])
def api_update_product(pid):
    data = request.json
    data["id"] = pid
    product = save_product(data)
    return jsonify({"success": True, "product": product})

@app.route("/api/products/<int:pid>", methods=["DELETE"])
def api_delete_product(pid):
    return jsonify({"success": delete_product(pid)})

# API ORDERS
@app.route("/api/orders", methods=["GET"])
def api_get_orders():
    return jsonify(get_all_orders())

@app.route("/api/orders", methods=["POST"])
def api_create_order():
    data = request.json
    order = save_order(data)
    return jsonify({"success": True, "order": order})

@app.route("/api/orders/<int:uid>", methods=["GET"])
def api_get_user_orders(uid):
    return jsonify(get_orders_by_user(uid))

@app.route("/api/orders/<int:oid>/status", methods=["PUT"])
def api_update_order_status(oid):
    data = request.json
    key = f"{ORDERS_KEY}:{oid}"
    if redis_client.exists(key):
        redis_client.hset(key, "status", data.get("status", "pending"))
        redis_client.hset(key, "updated_at", get_current_time())
        update_stats()
        return jsonify({"success": True})
    return jsonify({"error": "not found"}), 404

# API USERS
@app.route("/api/users/<int:uid>", methods=["GET"])
def api_get_user(uid):
    user = get_user(uid)
    if user:
        return jsonify(user)
    new_user = {
        "id": uid,
        "username": f"user_{uid}",
        "bonus": 0,
        "referrals": [],
        "referralCode": f"REF{uid:06d}",
        "isAdmin": uid in ADMIN_IDS
    }
    return jsonify(save_user(new_user))

@app.route("/api/users/<int:uid>", methods=["PUT"])
def api_update_user(uid):
    data = request.json
    data["id"] = uid
    return jsonify({"success": True, "user": save_user(data)})

# API PROMOS
@app.route("/api/promos", methods=["GET"])
def api_get_promos():
    return jsonify(get_all_promos())

@app.route("/api/promos", methods=["POST"])
def api_create_promo():
    data = request.json
    return jsonify({"success": True, "promo": save_promo(data)})

@app.route("/api/promos/<code>/apply", methods=["POST"])
def api_apply_promo(code):
    key = f"{PROMOS_KEY}:{code}"
    promo = redis_client.hgetall(key)
    if not promo:
        return jsonify({"error": "not found"}), 404
    used = int(promo.get("used", 0))
    uses = int(promo.get("uses", 0))
    discount = int(promo.get("discount", 0))
    if used >= uses:
        return jsonify({"error": "limit reached"}), 400
    redis_client.hincrby(key, "used", 1)
    return jsonify({"success": True, "discount": discount})

# API STATS
@app.route("/api/stats", methods=["GET"])
def api_get_stats():
    return jsonify(get_stats())

@app.route("/api/check-admin", methods=["GET"])
def api_check_admin():
    tg_id = request.args.get("tg_id")
    try:
        tg_id = int(tg_id)
        return jsonify({"isAdmin": tg_id in ADMIN_IDS})
    except:
        return jsonify({"isAdmin": False})

# INIT DATA
def init_sample_data():
    if not get_all_products():
        for p in [
            {"name": "Жидкость Mango", "category": "liquids", "price": 450, "stock": 10, "description": "Вкусный манго", "emoji": "🥭"},
            {"name": "Картридж JUUL", "category": "cartridges", "price": 300, "stock": 20, "description": "Оригинальные картриджи", "emoji": "💨"},
            {"name": "Под RELX Mint", "category": "pods", "price": 280, "stock": 12, "description": "Мятный вкус", "emoji": "🔥"},
            {"name": "Vaporesso XROS 3", "category": "devices", "price": 2800, "stock": 5, "description": "Компактная POD-система", "emoji": "⚡"}
        ]:
            save_product(p)
        print("✅ Sample products added")
    update_stats()

if __name__ == "__main__":
    print("🚀 Vape Shop Server starting...")
    init_sample_data()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    print(f"🌐 Running on port {port} | Debug={debug}")
    print(f"👑 Admin IDs: {ADMIN_IDS}")
    app.run(host="0.0.0.0", port=port, debug=debug)
