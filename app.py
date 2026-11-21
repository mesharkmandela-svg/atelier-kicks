from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
import sqlite3
import os
import time

app = Flask(__name__)
app.secret_key = "atelier-kicks-flagship-engine-2026"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "store.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "images")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

USD_TO_KES = 129.0

PROMO_CODES = {
    "KICKS15": 0.15,
    "VIP25": 0.25,
    "FIRST10": 0.10,
}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sneakers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            colorway TEXT NOT NULL,
            accent_hex TEXT NOT NULL,
            badge TEXT NOT NULL,
            sizes TEXT NOT NULL,
            image_file TEXT NOT NULL,
            weight_g INTEGER NOT NULL,
            drop_mm INTEGER NOT NULL,
            description TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sneaker_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            rating INTEGER NOT NULL,
            fit TEXT NOT NULL,
            comment TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            email TEXT NOT NULL,
            city TEXT NOT NULL,
            payment_method TEXT DEFAULT 'Card',
            mpesa_phone TEXT,
            currency TEXT DEFAULT 'USD',
            items_summary TEXT NOT NULL,
            discount_code TEXT,
            total REAL NOT NULL,
            status TEXT DEFAULT 'Paid & Processing',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    existing_cols = [row["name"] for row in cur.execute("PRAGMA table_info(orders)").fetchall()]
    if "payment_method" not in existing_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'Card'")
    if "mpesa_phone" not in existing_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN mpesa_phone TEXT")
    if "currency" not in existing_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN currency TEXT DEFAULT 'USD'")

    cur.execute("SELECT COUNT(*) AS cnt FROM sneakers")
    if cur.fetchone()["cnt"] == 0:
        catalog = [
            ("Air Pulse Alphafly Pro", "NIKE-STYLE", "Running", 245.00, "Volt / Carbon Black", "#a3e635", "RACE DAY", "40,41,42,43,44,45", "alphafly.jpg", 198, 8, "Dual forefoot air pods paired with a full-length carbon propulsion plate for marathon speed."),
            ("Adizero Prime X Strung", "ADIDAS-STYLE", "Running", 230.00, "Core Black / Solar Red", "#ef4444", "BESTSELLER", "40,41,42,43,44", "adizero.jpg", 205, 8, "Data-driven Strung textile upper locked onto triple-layer high-rebound Lightstrike foam."),
            ("Dunk Retro High '85", "NIKE-STYLE", "Lifestyle", 135.00, "University Red / Sail", "#dc2626", "ICONIC", "39,40,41,42,43,44,45", "dunk.jpg", 380, 10, "Crisp full-grain leather overlays and classic pivot-circle outsole for everyday street rotation."),
            ("Samba OG Terrace", "ADIDAS-STYLE", "Lifestyle", 115.00, "Shadow Olive / Gum", "#4d7c0f", "LIMITED", "40,41,42,43,45", "samba.jpg", 340, 7, "Indoor football icon crafted with supple leather, suede T-toe cap, and natural gum rubber sole."),
            ("ZoomX Terra Kiger 9", "NIKE-STYLE", "Trail", 165.00, "Canyon Rust / Stone", "#c2410c", "ALL-TERRAIN", "41,42,43,44,45", "kiger.jpg", 285, 4, "Multi-directional high-abrasion lugs and rock-plate protection built for technical ridge runs."),
            ("Terrex Agravic Speed", "ADIDAS-STYLE", "Trail", 175.00, "Slate Blue / Amber", "#0284c7", "NEW DROP", "40,42,43,44", "terrex.jpg", 270, 6, "Continental rubber grip and gusseted tongue engineered for wet rock and fast descents."),
            ("Jordan Court 1 Low OG", "JORDAN-STYLE", "Basketball", 150.00, "Obsidian / Ice White", "#1d4ed8", "COURT CLASSIC", "40,41,42,43,44,45", "jordan1.jpg", 395, 10, "Encapsulated heel air cushioning and timeless wings heel branding in a low-cut profile."),
            ("AE 1 Velocity Mid", "ADIDAS-STYLE", "Basketball", 140.00, "Acid Lime / Jet Black", "#84cc16", "PRO HOOPS", "41,42,43,44,45,46", "ae1.jpg", 410, 9, "Honeycomb TPU support wing delivering explosive lateral containment on hardwood courts."),
            ("New Balance 990v6 Made", "NB-STYLE", "Lifestyle", 215.00, "Castlerock Grey / Silver", "#71717a", "HERITAGE", "40,41,42,43,44,45", "nb990.jpg", 360, 8, "Pigskin suede and breathable mesh paired with FuelCell midsole foam for all-day comfort."),
            ("Cloudmonster Hyper", "ON-STYLE", "Running", 195.00, "Glacier White / Cobalt", "#2563eb", "MAX CUSHION", "40,41,42,43,44", "cloud.jpg", 230, 6, "Oversized CloudTec pods combined with dual-density Helion superfoam for effortless road miles."),
            ("Gazelle Indoor Pro", "ADIDAS-STYLE", "Lifestyle", 125.00, "Collegiate Burgundy / Cream", "#9f1239", "TRENDING", "39,40,41,42,43,44", "gazelle.jpg", 330, 7, "Translucent gum wrap outsole and velvety suede upper reviving 1970s training heritage."),
            ("Metcon 9 Amp Trainer", "NIKE-STYLE", "Training", 155.00, "Graphite / Electric Gold", "#eab308", "GYM READY", "40,41,42,43,44,45", "metcon.jpg", 355, 4, "Wide flat Hyperlift heel plate and rope-wrap rubber sidewall built for heavy lifting and HIIT."),
        ]
        cur.executemany(
            """
            INSERT INTO sneakers (name, brand, category, price, colorway, accent_hex, badge, sizes, image_file, weight_g, drop_mm, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            catalog,
        )

    conn.commit()
    conn.close()


def get_cart():
    return session.setdefault("cart", [])


def get_wishlist():
    return session.setdefault("wishlist", [])


def get_currency():
    return session.setdefault("currency", "USD")


def format_price(usd_amount):
    curr = get_currency()
    if curr == "KES":
        kes_val = round(float(usd_amount) * USD_TO_KES)
        return f"KES {kes_val:,}"
    return f"${float(usd_amount):,.2f}"


@app.context_processor
def inject_globals():
    cart = get_cart()
    wishlist = get_wishlist()
    subtotal = sum(item["price"] * item["qty"] for item in cart)
    return {
        "cart_items": cart,
        "cart_subtotal": subtotal,
        "cart_count": sum(item["qty"] for item in cart),
        "wishlist_count": len(wishlist),
        "currency": get_currency(),
        "usd_to_kes": USD_TO_KES,
        "format_price": format_price,
    }


@app.route("/currency/<curr_code>", methods=["POST"])
def switch_currency(curr_code):
    if curr_code in ("USD", "KES"):
        session["currency"] = curr_code
        session.modified = True
    return redirect(request.referrer or url_for("home"))


@app.route("/")
def home():
    conn = get_db()
    featured = conn.execute("SELECT * FROM sneakers LIMIT 6").fetchall()
    conn.close()
    return render_template("index.html", featured=featured, wishlist=get_wishlist())


@app.route("/lookbook")
def lookbook():
    conn = get_db()
    sneakers = conn.execute("SELECT * FROM sneakers ORDER BY id ASC").fetchall()
    conn.close()
    return render_template("lookbook.html", sneakers=sneakers, wishlist=get_wishlist())


@app.route("/shop")
def shop():
    brand = request.args.get("brand", "ALL")
    category = request.args.get("category", "ALL")
    sort = request.args.get("sort", "featured")
    max_price = request.args.get("max_price", "")
    q = request.args.get("q", "").strip().lower()

    query = "SELECT * FROM sneakers WHERE 1=1"
    params = []

    if brand != "ALL":
        query += " AND brand = ?"
        params.append(brand)
    if category != "ALL":
        query += " AND category = ?"
        params.append(category)
    if max_price and max_price.isdigit():
        query += " AND price <= ?"
        params.append(float(max_price))
    if q:
        query += " AND (LOWER(name) LIKE ? OR LOWER(colorway) LIKE ? OR LOWER(brand) LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like])

    if sort == "price_asc":
        query += " ORDER BY price ASC"
    elif sort == "price_desc":
        query += " ORDER BY price DESC"
    elif sort == "newest":
        query += " ORDER BY id DESC"
    else:
        query += " ORDER BY id ASC"

    conn = get_db()
    sneakers = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "shop.html",
        sneakers=sneakers,
        selected_brand=brand,
        selected_category=category,
        selected_sort=sort,
        max_price=max_price,
        search_q=request.args.get("q", ""),
        wishlist=get_wishlist(),
    )


@app.route("/sneaker/<int:sneaker_id>", methods=["GET", "POST"])
def sneaker_detail(sneaker_id):
    conn = get_db()
    if request.method == "POST":
        author = request.form.get("author", "").strip() or "Verified Buyer"
        rating = max(1, min(5, int(request.form.get("rating", 5))))
        fit = request.form.get("fit", "True to size")
        comment = request.form.get("comment", "").strip()
        if comment:
            conn.execute(
                "INSERT INTO reviews (sneaker_id, author, rating, fit, comment) VALUES (?, ?, ?, ?, ?)",
                (sneaker_id, author, rating, fit, comment),
            )
            conn.commit()
        conn.close()
        return redirect(url_for("sneaker_detail", sneaker_id=sneaker_id))

    shoe = conn.execute("SELECT * FROM sneakers WHERE id = ?", (sneaker_id,)).fetchone()
    if not shoe:
        conn.close()
        return "Sneaker not found", 404

    reviews = conn.execute("SELECT * FROM reviews WHERE sneaker_id = ? ORDER BY id DESC", (sneaker_id,)).fetchall()
    conn.close()

    avg_rating = round(sum(r["rating"] for r in reviews) / len(reviews), 1) if reviews else 5.0
    sizes = shoe["sizes"].split(",")
    return render_template(
        "detail.html",
        shoe=shoe,
        sizes=sizes,
        reviews=reviews,
        avg_rating=avg_rating,
        in_wishlist=sneaker_id in get_wishlist(),
    )


@app.route("/wishlist")
def wishlist_page():
    ids = get_wishlist()
    sneakers = []
    if ids:
        placeholders = ",".join("?" for _ in ids)
        conn = get_db()
        sneakers = conn.execute(f"SELECT * FROM sneakers WHERE id IN ({placeholders})", ids).fetchall()
        conn.close()
    return render_template("wishlist.html", sneakers=sneakers)


@app.route("/wishlist/toggle/<int:sneaker_id>", methods=["POST"])
def toggle_wishlist(sneaker_id):
    wishlist = get_wishlist()
    if sneaker_id in wishlist:
        wishlist.remove(sneaker_id)
    else:
        wishlist.append(sneaker_id)
    session.modified = True
    return redirect(request.referrer or url_for("shop"))


@app.route("/cart/add/<int:sneaker_id>", methods=["POST"])
def add_to_cart(sneaker_id):
    conn = get_db()
    shoe = conn.execute("SELECT * FROM sneakers WHERE id = ?", (sneaker_id,)).fetchone()
    conn.close()
    if not shoe:
        return redirect(url_for("shop"))

    size = request.form.get("size", "42")
    qty = max(1, int(request.form.get("qty", 1)))
    cart = get_cart()

    for item in cart:
        if item["id"] == shoe["id"] and item["size"] == size:
            item["qty"] += qty
            session.modified = True
            return redirect(url_for("view_cart"))

    cart.append({
        "id": shoe["id"],
        "name": shoe["name"],
        "brand": shoe["brand"],
        "price": float(shoe["price"]),
        "colorway": shoe["colorway"],
        "accent_hex": shoe["accent_hex"],
        "size": size,
        "qty": qty,
    })
    session.modified = True
    return redirect(url_for("view_cart"))


@app.route("/cart/update/<int:index>/<action>", methods=["POST"])
def update_cart_item(index, action):
    cart = get_cart()
    if 0 <= index < len(cart):
        if action == "inc":
            cart[index]["qty"] += 1
        elif action == "dec":
            cart[index]["qty"] -= 1
            if cart[index]["qty"] <= 0:
                cart.pop(index)
        elif action == "remove":
            cart.pop(index)
        session.modified = True
    return redirect(request.referrer or url_for("view_cart"))


@app.route("/cart", methods=["GET", "POST"])
def view_cart():
    cart = get_cart()
    promo = session.get("promo_code", "")
    discount_rate = PROMO_CODES.get(promo, 0.0)

    subtotal = sum(item["price"] * item["qty"] for item in cart)
    discount_amt = round(subtotal * discount_rate, 2)
    after_discount = subtotal - discount_amt
    shipping = 0.00 if after_discount >= 200 or after_discount == 0 else 15.00
    total = round(after_discount + shipping, 2)
    confirmed_order = None

    if request.method == "POST":
        form_type = request.form.get("form_type", "checkout")
        if form_type == "promo":
            code = request.form.get("promo_code", "").strip().upper()
            session["promo_code"] = code if code in PROMO_CODES else ""
            session.modified = True
            return redirect(url_for("view_cart"))

        if form_type == "checkout" and cart:
            customer_name = request.form.get("customer_name", "").strip()
            email = request.form.get("email", "").strip()
            city = request.form.get("city", "").strip()
            payment_method = request.form.get("payment_method", "M-PESA Express")
            mpesa_phone = request.form.get("mpesa_phone", "").strip()
            curr = get_currency()
            summary = ", ".join(f"{i['name']} (EU {i['size']} x{i['qty']})" for i in cart)

            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO orders (customer_name, email, city, payment_method, mpesa_phone, currency, items_summary, discount_code, total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (customer_name, email, city, payment_method, mpesa_phone or None, curr, summary, promo or None, total),
            )
            order_id = cur.lastrowid
            conn.commit()
            conn.close()

            confirmed_order = {
                "id": order_id,
                "customer_name": customer_name,
                "city": city,
                "payment_method": payment_method,
                "mpesa_phone": mpesa_phone,
                "total_formatted": format_price(total),
            }
            session["cart"] = []
            session["promo_code"] = ""
            session.modified = True

    return render_template(
        "cart.html",
        cart=get_cart() if confirmed_order else cart,
        subtotal=subtotal,
        discount_amt=discount_amt,
        promo_code=promo,
        shipping=shipping,
        total=total,
        confirmed_order=confirmed_order,
    )


@app.route("/orders")
def orders_page():
    conn = get_db()
    orders = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("orders.html", orders=orders)


@app.route("/admin", methods=["GET", "POST"])
def admin_page():
    conn = get_db()
    if request.method == "POST":
        action = request.form.get("action", "create")
        if action == "create":
            name = request.form.get("name", "").strip()
            brand = request.form.get("brand", "NIKE-STYLE").strip()
            category = request.form.get("category", "Lifestyle").strip()
            price = float(request.form.get("price", 150))
            colorway = request.form.get("colorway", "Black / White").strip()
            accent_hex = request.form.get("accent_hex", "#111111").strip()
            badge = request.form.get("badge", "NEW DROP").strip().upper()
            sizes = request.form.get("sizes", "40,41,42,43,44").strip()
            weight_g = int(request.form.get("weight_g", 300))
            drop_mm = int(request.form.get("drop_mm", 8))
            description = request.form.get("description", "").strip()

            image_file = "custom.jpg"
            uploaded = request.files.get("shoe_photo")
            if uploaded and uploaded.filename and allowed_file(uploaded.filename):
                safe_name = secure_filename(uploaded.filename)
                unique_name = f"{int(time.time())}_{safe_name}"
                uploaded.save(os.path.join(UPLOAD_FOLDER, unique_name))
                image_file = unique_name

            if name:
                conn.execute(
                    """
                    INSERT INTO sneakers (name, brand, category, price, colorway, accent_hex, badge, sizes, image_file, weight_g, drop_mm, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, brand, category, price, colorway, accent_hex, badge, sizes, image_file, weight_g, drop_mm, description),
                )
                conn.commit()
        elif action == "delete":
            sneaker_id = int(request.form.get("sneaker_id", 0))
            conn.execute("DELETE FROM sneakers WHERE id = ?", (sneaker_id,))
            conn.commit()

        conn.close()
        return redirect(url_for("admin_page"))

    sneakers = conn.execute("SELECT * FROM sneakers ORDER BY id DESC").fetchall()
    orders = conn.execute("SELECT * FROM orders").fetchall()
    conn.close()

    total_revenue = sum(o["total"] for o in orders)
    return render_template("admin.html", sneakers=sneakers, orders_count=len(orders), total_revenue=total_revenue)


@app.route("/api/sneakers/<int:sneaker_id>")
def api_sneaker(sneaker_id):
    conn = get_db()
    shoe = conn.execute("SELECT * FROM sneakers WHERE id = ?", (sneaker_id,)).fetchone()
    conn.close()
    if not shoe:
        return jsonify({"error": "Not found"}), 404
    data = dict(shoe)
    data["formatted_price"] = format_price(shoe["price"])
    return jsonify(data)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
