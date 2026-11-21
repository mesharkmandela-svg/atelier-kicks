import base64
from datetime import datetime
import json
import os
import sqlite3
import uuid

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
import requests
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "atelier-kicks-studio-secret-2026")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "store.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "images")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
USD_TO_KES = float(os.getenv("USD_TO_KES", "129.0"))


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_currency() -> str:
    curr = session.get("currency", "KES")
    return curr if curr in ("KES", "USD") else "KES"


def format_price(price_usd: float) -> str:
    val = float(price_usd or 0)
    curr = get_currency()
    if curr == "KES":
        kes_val = round(val * USD_TO_KES)
        return f"KES {kes_val:,}"
    return f"${val:,.2f}"


app.jinja_env.globals["format_price"] = format_price


DEFAULT_SNEAKERS = [
    (
        "Air Zoom Alphafly Next% 3",
        "Nike-Style",
        "Running",
        285.0,
        "CARBON RACE",
        "#FF4D1C",
        "alphafly.png",
        "39,40,41,42,43,44,45",
        12,
        "Dual Air Zoom units paired with full-length carbon fiber plate and ZoomX foam for marathon propulsion.",
        1,
    ),
    (
        "Samba OG Terrace",
        "Adidas-Style",
        "Lifestyle",
        115.0,
        "TERRACE ICON",
        "#0D1512",
        "samba.png",
        "39,40,41,42,43,44",
        18,
        "Low-profile full-grain leather upper with suede T-toe overlay and gum rubber outsole.",
        1,
    ),
    (
        "XT-6 Gore-Tex Trail",
        "Salomon-Style",
        "Trail",
        220.0,
        "ALL-TERRAIN",
        "#16231E",
        "xt6.png",
        "40,41,42,43,44,45",
        9,
        "Weather-sealed membrane, Quicklace lock system, and Agile Chassis Skeleton for technical mountain terrain.",
        1,
    ),
    (
        "Adizero Prime X Strung",
        "Adidas-Style",
        "Running",
        230.0,
        "HIGH STACK",
        "#E63E10",
        "primex.png",
        "40,41,42,43,44",
        7,
        "Data-driven Strung textile upper locked onto high-rebound Lightstrike Pro foam for long-distance tempo runs.",
        1,
    ),
    (
        "Dunk High Retro Varsity",
        "Nike-Style",
        "Basketball",
        135.0,
        "COURT ARCHIVE",
        "#0D1512",
        "dunkhigh.png",
        "39,40,41,42,43,44,45",
        14,
        "Crisp heritage leather paneling, padded high-top collar, and classic pivot-circle rubber tread.",
        1,
    ),
    (
        "990v6 Made in USA",
        "New Balance-Style",
        "Lifestyle",
        200.0,
        "STUDIO CRAFT",
        "#16231E",
        "990v6.png",
        "40,41,42,43,44,45",
        11,
        "Pigskin suede and breathable mesh over FuelCell midsole cushioning for all-day architectural comfort.",
        1,
    ),
    (
        "Gel-Kayano 31 Stability",
        "ASICS-Style",
        "Running",
        165.0,
        "DAILY TRAINER",
        "#0D1512",
        "kayano31.png",
        "39,40,41,42,43,44",
        15,
        "4D Guidance System stability paired with FF Blast Plus Eco cushioning and PureGel heel impact absorption.",
        0,
    ),
    (
        "Cloudultra 2 Endurance",
        "On-Style",
        "Trail",
        180.0,
        "ULTRA READY",
        "#FF4D1C",
        "cloudultra2.png",
        "40,41,42,43,44",
        8,
        "Flip-tongue sock fit, dual-layer Helion superfoam, and Missiongrip lugs built for endurance trail miles.",
        0,
    ),
    (
        "AE 1 Low Hardwood",
        "Adidas-Style",
        "Basketball",
        120.0,
        "HARDWOOD",
        "#0D1512",
        "ae1.png",
        "40,41,42,43,44,45",
        13,
        "Generative support wing and Jet Boost + Lightstrike hybrid midsole engineered for explosive court cuts.",
        0,
    ),
    (
        "Gazelle Indoor Court",
        "Adidas-Style",
        "Lifestyle",
        125.0,
        "CLASSIC",
        "#16231E",
        "gazelle.png",
        "39,40,41,42,43,44",
        16,
        "Supple suede upper, translucent gum sole, and gold foil branding inspired by indoor training heritage.",
        0,
    ),
    (
        "Vaporfly Next% 3 Proto",
        "Nike-Style",
        "Running",
        260.0,
        "RACE DAY",
        "#E63E10",
        "vaporfly3.png",
        "40,41,42,43,44",
        6,
        "Waffle-inspired outsole traction, tapered carbon Flyplate, and responsive ZoomX foam for race-day speed.",
        0,
    ),
    (
        "Speedgoat 5 Vibram",
        "Hoka-Style",
        "Trail",
        155.0,
        "GRIP LAB",
        "#0D1512",
        "speedgoat5.png",
        "40,41,42,43,44,45",
        10,
        "Vibram Megagrip with Traction Lug and CMEVA midsole designed for steep ascents and loose descents.",
        0,
    ),
]


def init_db() -> None:
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sneakers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            badge TEXT NOT NULL,
            accent_hex TEXT NOT NULL,
            image_file TEXT NOT NULL,
            sizes TEXT NOT NULL,
            stock INTEGER NOT NULL DEFAULT 10,
            description TEXT NOT NULL,
            featured INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sneaker_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            shipping_address TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            mpesa_phone TEXT,
            total_usd REAL NOT NULL,
            status TEXT NOT NULL,
            items_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    count = cur.execute("SELECT COUNT(*) FROM sneakers").fetchone()[0]
    if count == 0:
        cur.executemany(
            """
            INSERT INTO sneakers
                (name, brand, category, price, badge, accent_hex, image_file, sizes, stock, description, featured)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            DEFAULT_SNEAKERS,
        )

    conn.commit()
    conn.close()


init_db()


def get_cart_summary() -> tuple[list[dict], float, float, float, int]:
    cart = session.get("cart", {})
    conn = get_db()
    items = []
    subtotal = 0.0
    total_qty = 0

    for key, entry in cart.items():
        sid = entry.get("sneaker_id")
        size = entry.get("size", "42")
        qty = max(1, int(entry.get("qty", 1)))
        row = conn.execute("SELECT * FROM sneakers WHERE id = ?", (sid,)).fetchone()
        if row:
            line_total = float(row["price"]) * qty
            subtotal += line_total
            total_qty += qty
            items.append(
                {
                    "key": key,
                    "sneaker": dict(row),
                    "size": size,
                    "qty": qty,
                    "line_total": line_total,
                }
            )
    conn.close()

    shipping = 0.0 if (subtotal == 0 or subtotal >= 200.0) else 15.0
    total = subtotal + shipping
    return items, subtotal, shipping, total, total_qty


@app.context_processor
def inject_globals():
    _, _, _, _, cart_count = get_cart_summary()
    wishlist_ids = session.get("wishlist", [])
    return {
        "currency": get_currency(),
        "cart_count": cart_count,
        "wishlist_count": len(wishlist_ids),
        "wishlist_ids": wishlist_ids,
    }


@app.route("/")
def home():
    conn = get_db()
    sneakers = [dict(r) for r in conn.execute("SELECT * FROM sneakers ORDER BY id ASC").fetchall()]
    featured = [s for s in sneakers if s.get("featured")] or sneakers[:6]
    conn.close()
    return render_template("index.html", sneakers=sneakers, featured=featured)


@app.route("/shop")
def shop():
    q = (request.args.get("q") or "").strip()
    category = request.args.get("category") or "All"
    brand = request.args.get("brand") or "All"
    sort_by = request.args.get("sort") or "featured"

    conn = get_db()
    all_rows = [dict(r) for r in conn.execute("SELECT * FROM sneakers").fetchall()]
    categories = ["All"] + sorted({r["category"] for r in all_rows})
    brands = ["All"] + sorted({r["brand"] for r in all_rows})

    filtered = all_rows
    if q:
        ql = q.lower()
        filtered = [
            s
            for s in filtered
            if ql in s["name"].lower()
            or ql in s["brand"].lower()
            or ql in s["category"].lower()
            or ql in s["description"].lower()
        ]
    if category and category != "All":
        filtered = [s for s in filtered if s["category"] == category]
    if brand and brand != "All":
        filtered = [s for s in filtered if s["brand"] == brand]

    if sort_by == "price_asc":
        filtered.sort(key=lambda s: s["price"])
    elif sort_by == "price_desc":
        filtered.sort(key=lambda s: s["price"], reverse=True)
    elif sort_by == "newest":
        filtered.sort(key=lambda s: s["id"], reverse=True)
    else:
        filtered.sort(key=lambda s: (-int(s.get("featured", 0)), s["id"]))

    conn.close()
    return render_template(
        "shop.html",
        sneakers=filtered,
        categories=categories,
        brands=brands,
        q=q,
        selected_category=category,
        selected_brand=brand,
        sort_by=sort_by,
    )


@app.route("/lookbook")
def lookbook():
    conn = get_db()
    sneakers = [dict(r) for r in conn.execute("SELECT * FROM sneakers ORDER BY id ASC").fetchall()]
    conn.close()
    return render_template("lookbook.html", sneakers=sneakers)


@app.route("/sneaker/<int:sneaker_id>")
def sneaker_detail(sneaker_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM sneakers WHERE id = ?", (sneaker_id,)).fetchone()
    if not row:
        conn.close()
        flash("Silhouette not found in archive.")
        return redirect(url_for("shop"))

    reviews = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM reviews WHERE sneaker_id = ? ORDER BY id DESC", (sneaker_id,)
        ).fetchall()
    ]
    conn.close()

    avg_rating = (
        round(sum(r["rating"] for r in reviews) / len(reviews), 1) if reviews else None
    )
    return render_template(
        "detail.html",
        sneaker=dict(row),
        reviews=reviews,
        avg_rating=avg_rating,
    )


@app.route("/sneaker/<int:sneaker_id>/review", methods=["POST"])
def add_review(sneaker_id: int):
    author = (request.form.get("author") or "Anonymous").strip()
    rating = max(1, min(5, int(request.form.get("rating") or 5)))
    comment = (request.form.get("comment") or "").strip()
    if comment:
        conn = get_db()
        conn.execute(
            "INSERT INTO reviews (sneaker_id, author, rating, comment, created_at) VALUES (?, ?, ?, ?, ?)",
            (sneaker_id, author, rating, comment, datetime.utcnow().strftime("%Y-%m-%d %H:%M")),
        )
        conn.commit()
        conn.close()
        flash("Owner note logged.")
    return redirect(url_for("sneaker_detail", sneaker_id=sneaker_id))


@app.route("/currency", methods=["POST"])
def switch_currency():
    curr = (request.form.get("currency") or "KES").upper()
    if curr in ("KES", "USD"):
        session["currency"] = curr
        session.modified = True
    nxt = request.form.get("next") or url_for("home")
    if not nxt.startswith("/"):
        nxt = url_for("home")
    return redirect(nxt)


@app.route("/wishlist")
def wishlist():
    ids = session.get("wishlist", [])
    conn = get_db()
    sneakers = []
    for sid in ids:
        row = conn.execute("SELECT * FROM sneakers WHERE id = ?", (sid,)).fetchone()
        if row:
            sneakers.append(dict(row))
    conn.close()
    return render_template("wishlist.html", sneakers=sneakers)


@app.route("/wishlist/toggle/<int:sneaker_id>", methods=["POST"])
def toggle_wishlist(sneaker_id: int):
    wl = session.get("wishlist", [])
    if sneaker_id in wl:
        wl.remove(sneaker_id)
        flash("Removed from saved wishlist.")
    else:
        wl.append(sneaker_id)
        flash("Saved to wishlist.")
    session["wishlist"] = wl
    session.modified = True
    nxt = request.form.get("next") or url_for("shop")
    if not nxt.startswith("/"):
        nxt = url_for("shop")
    return redirect(nxt)


@app.route("/cart")
def cart_view():
    items, subtotal, shipping, total, _ = get_cart_summary()
    return render_template(
        "cart.html",
        items=items,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
    )


@app.route("/cart/add/<int:sneaker_id>", methods=["POST"])
def cart_add(sneaker_id: int):
    size = (request.form.get("size") or "42").strip()
    qty = max(1, int(request.form.get("qty") or 1))
    cart = session.get("cart", {})
    key = f"{sneaker_id}_{size}"
    if key in cart:
        cart[key]["qty"] = int(cart[key]["qty"]) + qty
    else:
        cart[key] = {"sneaker_id": sneaker_id, "size": size, "qty": qty}
    session["cart"] = cart
    session.modified = True
    flash(f"Added EU {size} to bag.")
    return redirect(request.referrer or url_for("shop"))


@app.route("/cart/remove/<path:item_key>", methods=["POST"])
def cart_remove(item_key: str):
    cart = session.get("cart", {})
    if item_key in cart:
        del cart[item_key]
        session["cart"] = cart
        session.modified = True
        flash("Item removed from bag.")
    return redirect(url_for("cart_view"))


def trigger_daraja_stk_push(phone: str, amount_kes: int, account_ref: str) -> tuple[bool, str]:
    consumer_key = os.getenv("MPESA_CONSUMER_KEY", "").strip()
    consumer_secret = os.getenv("MPESA_CONSUMER_SECRET", "").strip()
    shortcode = os.getenv("MPESA_SHORTCODE", "").strip()
    passkey = os.getenv("MPESA_PASSKEY", "").strip()
    callback_url = os.getenv("MPESA_CALLBACK_URL", "").strip()
    env = os.getenv("MPESA_ENV", "sandbox").lower()

    if not (consumer_key and consumer_secret and shortcode and passkey and callback_url):
        return True, "STK Prompt Queued (Sandbox / Ready)"

    clean_phone = "".join(ch for ch in phone if ch.isdigit())
    if clean_phone.startswith("0") and len(clean_phone) == 10:
        clean_phone = "254" + clean_phone[1:]
    elif len(clean_phone) == 9:
        clean_phone = "254" + clean_phone

    base_url = (
        "https://api.safaricom.co.ke"
        if env == "live"
        else "https://sandbox.safaricom.co.ke"
    )

    try:
        token_resp = requests.get(
            f"{base_url}/oauth/v1/generate?grant_type=client_credentials",
            auth=(consumer_key, consumer_secret),
            timeout=15,
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()

        payload = {
            "BusinessShortCode": shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerBuyGoodsOnline",
            "Amount": max(1, int(amount_kes)),
            "PartyA": clean_phone,
            "PartyB": shortcode,
            "PhoneNumber": clean_phone,
            "CallBackURL": callback_url,
            "AccountReference": account_ref[:12],
            "TransactionDesc": "Atelier Kicks Order",
        }
        stk_resp = requests.post(
            f"{base_url}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        stk_resp.raise_for_status()
        return True, "M-PESA STK Push Sent"
    except Exception as exc:
        return False, f"Daraja notice: {exc}"


@app.route("/checkout", methods=["POST"])
def checkout():
    items, subtotal, shipping, total, _ = get_cart_summary()
    if not items:
        flash("Your bag is empty.")
        return redirect(url_for("shop"))

    customer_name = (request.form.get("customer_name") or "Guest Client").strip()
    customer_email = (request.form.get("customer_email") or "").strip()
    shipping_address = (request.form.get("shipping_address") or "").strip()
    payment_method = (request.form.get("payment_method") or "mpesa").strip()
    mpesa_phone = (request.form.get("mpesa_phone") or "").strip()

    order_number = f"AK-{uuid.uuid4().hex[:8].upper()}"
    status = "Awaiting M-PESA PIN" if payment_method == "mpesa" else "Confirmed"

    if payment_method == "mpesa":
        amount_kes = round(total * USD_TO_KES)
        _, msg = trigger_daraja_stk_push(mpesa_phone, amount_kes, order_number)
        flash(f"Order {order_number} created — {msg}.")
    else:
        flash(f"Order {order_number} confirmed.")

    compact_items = [
        {
            "name": it["sneaker"]["name"],
            "size": it["size"],
            "qty": it["qty"],
            "price": it["sneaker"]["price"],
        }
        for it in items
    ]

    conn = get_db()
    conn.execute(
        """
        INSERT INTO orders
            (order_number, customer_name, customer_email, shipping_address, payment_method, mpesa_phone, total_usd, status, items_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_number,
            customer_name,
            customer_email,
            shipping_address,
            payment_method,
            mpesa_phone,
            total,
            status,
            json.dumps(compact_items),
            datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        ),
    )
    conn.commit()
    conn.close()

    session["cart"] = {}
    session.modified = True
    return redirect(url_for("orders_view"))


@app.route("/orders")
def orders_view():
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()]
    conn.close()
    for r in rows:
        try:
            r["items_list"] = json.loads(r.get("items_json") or "[]")
        except Exception:
            r["items_list"] = []
    return render_template("orders.html", orders=rows)


@app.route("/admin")
def admin_view():
    conn = get_db()
    sneakers = [dict(r) for r in conn.execute("SELECT * FROM sneakers ORDER BY id DESC").fetchall()]
    orders_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    conn.close()
    return render_template("admin.html", sneakers=sneakers, orders_count=orders_count)


@app.route("/admin/add", methods=["POST"])
def admin_add():
    name = (request.form.get("name") or "").strip()
    brand = (request.form.get("brand") or "Atelier").strip()
    category = (request.form.get("category") or "Lifestyle").strip()
    price = float(request.form.get("price") or 150.0)
    stock = max(0, int(request.form.get("stock") or 10))
    badge = (request.form.get("badge") or "NEW DROP").strip()
    sizes = (request.form.get("sizes") or "40,41,42,43,44").strip()
    description = (request.form.get("description") or "").strip()
    featured = 1 if request.form.get("featured") else 0

    image_file = "samba.png"
    file = request.files.get("image")
    if file and file.filename and allowed_file(file.filename):
        safe_name = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], safe_name))
        image_file = safe_name

    conn = get_db()
    conn.execute(
        """
        INSERT INTO sneakers
            (name, brand, category, price, badge, accent_hex, image_file, sizes, stock, description, featured)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            brand,
            category,
            price,
            badge,
            "#FF4D1C",
            image_file,
            sizes,
            stock,
            description,
            featured,
        ),
    )
    conn.commit()
    conn.close()
    flash(f"Published '{name}' to catalog.")
    return redirect(url_for("admin_view"))


@app.route("/admin/delete/<int:sneaker_id>", methods=["POST"])
def admin_delete(sneaker_id: int):
    conn = get_db()
    conn.execute("DELETE FROM sneakers WHERE id = ?", (sneaker_id,))
    conn.commit()
    conn.close()
    flash("Silhouette removed from catalog.")
    return redirect(url_for("admin_view"))


# --- INSTANT JSON API ENDPOINTS (Command Palette, Quick-View & Slide-Out Bag Drawer) ---
@app.route("/api/catalog")
def api_catalog():
    conn = get_db()
    rows = conn.execute("SELECT * FROM sneakers ORDER BY id ASC").fetchall()
    conn.close()
    items = []
    for r in rows:
        items.append(
            {
                "id": r["id"],
                "name": r["name"],
                "brand": r["brand"],
                "category": r["category"],
                "badge": r["badge"],
                "price_raw": r["price"],
                "price_formatted": format_price(r["price"]),
                "image_url": url_for("static", filename="images/" + r["image_file"]),
                "sizes": [s.strip() for s in r["sizes"].split(",") if s.strip()],
                "description": r["description"],
                "stock": r["stock"],
            }
        )
    return jsonify({"sneakers": items, "currency": get_currency()})


@app.route("/api/cart/state")
def api_cart_state():
    items, subtotal, _, _, total_qty = get_cart_summary()
    drawer_items = []
    for it in items:
        s = it["sneaker"]
        drawer_items.append(
            {
                "key": it["key"],
                "id": s["id"],
                "name": s["name"],
                "brand": s["brand"],
                "size": it["size"],
                "qty": it["qty"],
                "image_url": url_for("static", filename="images/" + s["image_file"]),
                "line_total_formatted": format_price(it["line_total"]),
            }
        )

    free_ship_threshold = 200.0
    remaining = max(0.0, free_ship_threshold - subtotal)
    progress_pct = min(100, int((subtotal / free_ship_threshold) * 100)) if subtotal > 0 else 0
    return jsonify(
        {
            "items": drawer_items,
            "count": total_qty,
            "subtotal_formatted": format_price(subtotal),
            "remaining_formatted": format_price(remaining),
            "free_shipping_unlocked": subtotal >= free_ship_threshold and subtotal > 0,
            "progress_pct": progress_pct,
        }
    )


@app.route("/api/cart/add/<int:sneaker_id>", methods=["POST"])
def api_cart_add(sneaker_id: int):
    data = request.get_json(silent=True) or request.form
    size = str(data.get("size", "42")).strip()
    qty = max(1, int(data.get("qty", 1)))
    cart = session.get("cart", {})
    key = f"{sneaker_id}_{size}"
    if key in cart:
        cart[key]["qty"] = int(cart[key]["qty"]) + qty
    else:
        cart[key] = {"sneaker_id": sneaker_id, "size": size, "qty": qty}
    session["cart"] = cart
    session.modified = True
    return api_cart_state()


if __name__ == "__main__":
    app.run(debug=True)