from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2 import pool
import psycopg2
import os
import jwt
import datetime
import redis
import json
import logging
from functools import wraps
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
CORS(app)

# =========================================================
# CONFIGURATION
# =========================================================
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(32).hex())
app.config["JWT_EXPIRATION_HOURS"] = 24

# =========================================================
# LOGGING SETUP
# =========================================================
if not os.path.exists('logs'):
    os.mkdir('logs')

file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240000, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('HAKS Shop startup')

# =========================================================
# DATABASE CONNECTION POOL
# =========================================================
db_pool = None

def init_db_pool():
    global db_pool
    try:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise Exception("DATABASE_URL not set")
        
        db_pool = pool.ThreadedConnectionPool(
            minconn=5,
            maxconn=20,
            dsn=db_url
        )
        app.logger.info("Database pool created successfully")
    except Exception as e:
        app.logger.error(f"Failed to create DB pool: {str(e)}")
        raise

def get_db_connection():
    try:
        return db_pool.getconn()
    except Exception as e:
        app.logger.error(f"Failed to get DB connection: {str(e)}")
        raise

def release_db_connection(conn):
    try:
        db_pool.putconn(conn)
    except Exception as e:
        app.logger.error(f"Failed to release DB connection: {str(e)}")

# =========================================================
# REDIS CACHE SETUP
# =========================================================
redis_client = None

def init_redis():
    global redis_client
    try:
        redis_url = os.environ.get("REDIS_URL")
        if redis_url:
            redis_client = redis.from_url(redis_url, decode_responses=True)
            redis_client.ping()
            app.logger.info("Redis connected successfully")
        else:
            app.logger.warning("REDIS_URL not set - caching disabled")
    except Exception as e:
        app.logger.warning(f"Redis connection failed: {str(e)} - continuing without cache")
        redis_client = None

# Cache decorator
def cache(timeout=300):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not redis_client:
                return f(*args, **kwargs)
            
            # Create cache key
            cache_key = f"{f.__name__}:{request.path}:{request.args.to_dict()}"
            
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    app.logger.info(f"Cache hit: {cache_key}")
                    return json.loads(cached)
            except Exception as e:
                app.logger.error(f"Cache read error: {str(e)}")
            
            result = f(*args, **kwargs)
            
            try:
                if isinstance(result, tuple):
                    data, status = result
                    redis_client.setex(cache_key, timeout, json.dumps(data))
                else:
                    redis_client.setex(cache_key, timeout, json.dumps(result))
            except Exception as e:
                app.logger.error(f"Cache write error: {str(e)}")
            
            return result
        return wrapper
    return decorator

# =========================================================
# RATE LIMITING
# =========================================================
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.environ.get("REDIS_URL", "memory://")
)

# =========================================================
# JWT AUTH DECORATOR
# =========================================================
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        
        if not token:
            return jsonify({"error": "Token missing"}), 401

        try:
            if token.startswith("Bearer "):
                token = token.split(" ")[1]
            
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            request.user_id = data["user_id"]
            request.is_admin = data.get("is_admin", False)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except Exception as e:
            app.logger.error(f"Token validation error: {str(e)}")
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)
    return decorated

# =========================================================
# ERROR HANDLERS
# =========================================================
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"Internal error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429

# =========================================================
# BASIC ROUTES
# =========================================================
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "Backend running",
        "version": "2.0",
        "features": ["connection_pooling", "caching", "rate_limiting"]
    }), 200

@app.route("/health", methods=["GET"])
def health():
    health_status = {
        "database": "unknown",
        "redis": "unknown"
    }
    
    # Check database
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        health_status["database"] = "healthy"
    except Exception as e:
        app.logger.error(f"DB health check failed: {str(e)}")
        health_status["database"] = "unhealthy"
    finally:
        if conn:
            release_db_connection(conn)
    
    # Check Redis
    if redis_client:
        try:
            redis_client.ping()
            health_status["redis"] = "healthy"
        except:
            health_status["redis"] = "unhealthy"
    else:
        health_status["redis"] = "disabled"
    
    status_code = 200 if health_status["database"] == "healthy" else 503
    return jsonify(health_status), status_code

# =========================================================
# AUTH ROUTES
# =========================================================
@app.route("/signup", methods=["POST"])
@limiter.limit("5 per hour")
def signup():
    conn = None
    try:
        data = request.get_json()
        
        # Validation
        required_fields = ["name", "email", "password"]
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400
        
        if len(data["password"]) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400
        
        hashed_password = generate_password_hash(data["password"])
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s) RETURNING id",
            (data["name"], data["email"], hashed_password)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        
        app.logger.info(f"New user registered: {data['email']}")
        return jsonify({"message": "Signup successful", "user_id": user_id}), 201
        
    except psycopg2.errors.UniqueViolation:
        if conn:
            conn.rollback()
        return jsonify({"error": "Email already exists"}), 409
    except Exception as e:
        if conn:
            conn.rollback()
        app.logger.error(f"Signup error: {str(e)}")
        return jsonify({"error": "Signup failed"}), 500
    finally:
        if conn:
            release_db_connection(conn)

@app.route("/login", methods=["POST"])
@limiter.limit("10 per hour")
def login():
    conn = None
    try:
        data = request.get_json()
        
        if not data.get("email") or not data.get("password"):
            return jsonify({"error": "Email and password required"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT id, name, password, is_admin FROM users WHERE email = %s",
            (data["email"],)
        )
        user = cur.fetchone()
        cur.close()
        
        if not user or not check_password_hash(user[2], data["password"]):
            return jsonify({"error": "Invalid email or password"}), 401
        
        # Generate JWT
        token = jwt.encode({
            "user_id": user[0],
            "is_admin": user[3] if user[3] else False,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=app.config["JWT_EXPIRATION_HOURS"])
        }, app.config["SECRET_KEY"], algorithm="HS256")
        
        app.logger.info(f"User logged in: {data['email']}")
        
        return jsonify({
            "token": token,
            "user_id": user[0],
            "name": user[1],
            "is_admin": user[3] if user[3] else False,
            "message": "Login successful"
        }), 200
        
    except Exception as e:
        app.logger.error(f"Login error: {str(e)}")
        return jsonify({"error": "Login failed"}), 500
    finally:
        if conn:
            release_db_connection(conn)

# =========================================================
# PRODUCT ROUTES
# =========================================================
@app.route("/products", methods=["GET"])
@cache(timeout=600)  # Cache for 10 minutes
def get_products():
    conn = None
    try:
        category = request.args.get("category")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        
        # Limit per_page to prevent abuse
        per_page = min(per_page, 100)
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get total count
        if category:
            cur.execute("SELECT COUNT(*) FROM products WHERE category = %s", (category,))
        else:
            cur.execute("SELECT COUNT(*) FROM products")
        total = cur.fetchone()[0]
        
        # Get paginated products
        if category:
            cur.execute("""
                SELECT id, name, price, category, image_url, stock
                FROM products
                WHERE category = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (category, per_page, offset))
        else:
            cur.execute("""
                SELECT id, name, price, category, image_url, stock
                FROM products
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))
        
        rows = cur.fetchall()
        cur.close()
        
        products = [{
            "id": r[0],
            "name": r[1],
            "price": float(r[2]),
            "category": r[3],
            "image_url": r[4],
            "stock": r[5]
        } for r in rows]
        
        return jsonify({
            "data": products,
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page
        }), 200
        
    except Exception as e:
        app.logger.error(f"Get products error: {str(e)}")
        return jsonify({"error": "Failed to fetch products"}), 500
    finally:
        if conn:
            release_db_connection(conn)

@app.route("/products/<int:product_id>", methods=["GET"])
@cache(timeout=600)
def get_product(product_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, name, price, category, image_url, stock, description
            FROM products
            WHERE id = %s
        """, (product_id,))
        
        row = cur.fetchone()
        cur.close()
        
        if not row:
            return jsonify({"error": "Product not found"}), 404
        
        product = {
            "id": row[0],
            "name": row[1],
            "price": float(row[2]),
            "category": row[3],
            "image_url": row[4],
            "stock": row[5],
            "description": row[6] if len(row) > 6 else None
        }
        
        return jsonify(product), 200
        
    except Exception as e:
        app.logger.error(f"Get product error: {str(e)}")
        return jsonify({"error": "Failed to fetch product"}), 500
    finally:
        if conn:
            release_db_connection(conn)

# =========================================================
# CART ROUTES
# =========================================================
@app.route("/add-to-cart", methods=["POST"])
@limiter.limit("30 per minute")
def add_to_cart():
    conn = None
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        product_id = data.get("product_id")
        quantity = data.get("quantity", 1)
        
        if not user_id or not product_id:
            return jsonify({"error": "user_id and product_id required"}), 400
        
        if quantity < 1 or quantity > 99:
            return jsonify({"error": "Invalid quantity"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if product exists and has stock
        cur.execute("SELECT stock FROM products WHERE id = %s", (product_id,))
        product = cur.fetchone()
        
        if not product:
            return jsonify({"error": "Product not found"}), 404
        
        if product[0] < quantity:
            return jsonify({"error": "Insufficient stock"}), 400
        
        # Add or update cart
        cur.execute(
            "SELECT id, quantity FROM cart WHERE user_id = %s AND product_id = %s",
            (user_id, product_id)
        )
        existing = cur.fetchone()
        
        if existing:
            new_quantity = existing[1] + quantity
            cur.execute(
                "UPDATE cart SET quantity = %s WHERE id = %s",
                (new_quantity, existing[0])
            )
        else:
            cur.execute(
                "INSERT INTO cart (user_id, product_id, quantity) VALUES (%s, %s, %s)",
                (user_id, product_id, quantity)
            )
        
        conn.commit()
        cur.close()
        
        app.logger.info(f"Product {product_id} added to cart for user {user_id}")
        return jsonify({"message": "Product added to cart"}), 200
        
    except Exception as e:
        if conn:
            conn.rollback()
        app.logger.error(f"Add to cart error: {str(e)}")
        return jsonify({"error": "Failed to add to cart"}), 500
    finally:
        if conn:
            release_db_connection(conn)

@app.route("/cart", methods=["GET"])
def get_cart():
    conn = None
    try:
        user_id = request.args.get("user_id")
        
        if not user_id:
            return jsonify({"error": "user_id required"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT c.id, p.id, p.name, p.price, p.image_url, c.quantity, p.stock
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = %s
        """, (user_id,))
        
        rows = cur.fetchall()
        cur.close()
        
        cart_items = [{
            "cart_id": r[0],
            "product_id": r[1],
            "name": r[2],
            "price": float(r[3]),
            "image_url": r[4],
            "quantity": r[5],
            "in_stock": r[6] >= r[5]
        } for r in rows]
        
        total = sum(item["price"] * item["quantity"] for item in cart_items)
        
        return jsonify({
            "items": cart_items,
            "total": total,
            "count": len(cart_items)
        }), 200
        
    except Exception as e:
        app.logger.error(f"Get cart error: {str(e)}")
        return jsonify({"error": "Failed to fetch cart"}), 500
    finally:
        if conn:
            release_db_connection(conn)

@app.route("/cart/<int:cart_id>", methods=["DELETE"])
def remove_from_cart(cart_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("DELETE FROM cart WHERE id = %s", (cart_id,))
        conn.commit()
        cur.close()
        
        return jsonify({"message": "Item removed from cart"}), 200
        
    except Exception as e:
        if conn:
            conn.rollback()
        app.logger.error(f"Remove from cart error: {str(e)}")
        return jsonify({"error": "Failed to remove item"}), 500
    finally:
        if conn:
            release_db_connection(conn)

# =========================================================
# ADMIN ROUTES
# =========================================================
@app.route("/admin/login", methods=["POST"])
@limiter.limit("5 per hour")
def admin_login():
    conn = None
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT id, name, password, is_admin FROM users WHERE email = %s",
            (data.get("email"),)
        )
        user = cur.fetchone()
        cur.close()
        
        if not user or not check_password_hash(user[2], data.get("password", "")):
            return jsonify({"error": "Invalid credentials"}), 401
        
        if not user[3]:
            return jsonify({"error": "Access Denied: Admins only"}), 403
        
        token = jwt.encode({
            "user_id": user[0],
            "is_admin": True,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config["SECRET_KEY"], algorithm="HS256")
        
        return jsonify({
            "admin_id": user[0],
            "name": user[1],
            "token": token
        }), 200
        
    except Exception as e:
        app.logger.error(f"Admin login error: {str(e)}")
        return jsonify({"error": "Login failed"}), 500
    finally:
        if conn:
            release_db_connection(conn)

@app.route("/admin/stats", methods=["GET"])
@cache(timeout=60)  # Cache for 1 minute
def admin_stats():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Revenue
        cur.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders")
        revenue = float(cur.fetchone()[0])
        
        # Orders
        cur.execute("SELECT COUNT(*) FROM orders")
        orders_count = cur.fetchone()[0]
        
        # Products
        cur.execute("SELECT COUNT(*) FROM products")
        products_count = cur.fetchone()[0]
        
        # Users
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]
        
        cur.close()
        
        return jsonify({
            "revenue": revenue,
            "orders": orders_count,
            "products": products_count,
            "users": users_count
        }), 200
        
    except Exception as e:
        app.logger.error(f"Admin stats error: {str(e)}")
        return jsonify({"error": "Failed to fetch stats"}), 500
    finally:
        if conn:
            release_db_connection(conn)

@app.route("/admin/product", methods=["POST", "PUT", "DELETE"])
@token_required
def manage_product():
    if not request.is_admin:
        return jsonify({"error": "Admin access required"}), 403
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        if request.method == "POST":
            data = request.get_json()
            cur.execute("""
                INSERT INTO products (name, category, price, image_url, stock, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                data['name'],
                data['category'],
                data['price'],
                data['image_url'],
                data.get('stock', 0),
                data.get('description', '')
            ))
            product_id = cur.fetchone()[0]
            conn.commit()
            
            # Invalidate products cache
            if redis_client:
                try:
                    keys = redis_client.keys("get_products:*")
                    if keys:
                        redis_client.delete(*keys)
                except:
                    pass
            
            return jsonify({"message": "Product created", "id": product_id}), 201
        
        elif request.method == "DELETE":
            product_id = request.args.get("id")
            cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
            conn.commit()
            
            # Invalidate cache
            if redis_client:
                try:
                    keys = redis_client.keys("get_products:*")
                    if keys:
                        redis_client.delete(*keys)
                except:
                    pass
            
            return jsonify({"message": "Product deleted"}), 200
        
        cur.close()
        
    except Exception as e:
        if conn:
            conn.rollback()
        app.logger.error(f"Manage product error: {str(e)}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_connection(conn)

@app.route("/admin/orders", methods=["GET", "PUT"])
def manage_orders():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        if request.method == "GET":
            cur.execute("""
                SELECT o.id, u.name, o.total_amount, o.status, o.created_at
                FROM orders o
                JOIN users u ON o.user_id = u.id
                ORDER BY o.created_at DESC
                LIMIT 100
            """)
            rows = cur.fetchall()
            
            orders = [{
                "id": r[0],
                "customer": r[1],
                "amount": float(r[2]),
                "status": r[3],
                "date": r[4].isoformat() if r[4] else None
            } for r in rows]
            
            return jsonify(orders), 200
        
        elif request.method == "PUT":
            data = request.get_json()
            cur.execute(
                "UPDATE orders SET status = %s WHERE id = %s",
                (data['status'], data['order_id'])
            )
            conn.commit()
            return jsonify({"message": "Order updated"}), 200
        
        cur.close()
        
    except Exception as e:
        if conn:
            conn.rollback()
        app.logger.error(f"Manage orders error: {str(e)}")
        return jsonify({"error": "Failed to manage orders"}), 500
    finally:
        if conn:
            release_db_connection(conn)

# =========================================================
# INITIALIZE ON STARTUP
# =========================================================
@app.before_request
def startup():
    init_db_pool()
    init_redis()

# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    init_db_pool()
    init_redis()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
