import base64
from datetime import datetime
import json
import os
import re
import shutil
import sqlite3
import uuid

from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
import requests
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "atelier-kicks-studio-secret-2026")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", "").strip() or BASE_DIR
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "store.db")
STATIC_IMAGES_DIR = os.path.join(BASE_DIR, "static", "images")
os.makedirs(STATIC_IMAGES_DIR, exist_ok=True)

UPLOAD_FOLDER = (
    os.path.join(DATA_DIR, "uploads")
    if DATA_DIR != BASE_DIR
    else STATIC_IMAGES_DIR
)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
USD_TO_KES = float(os.getenv("USD_TO_KES", "129.0"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def is_admin_authenticated() -> bool:
    if not ADMIN_PASSWORD:
        return True
    return bool(session.get("admin_authed"))


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


KEYWORD_ALIASES = {
    "alphafly": ["alphafly"],
    "samba": ["samba"],
    "terrex": ["terrex", "xt6", "salomon", "trail"],
    "adizero": ["adizero", "primex", "prime"],
    "dunk": ["dunk", "dunkhigh"],
    "nb990": ["nb990", "990v6", "990"],
    "jordan1": ["jordan1", "jordan", "kayano", "kayano31"],
    "cloud": ["cloud", "cloudultra", "cloudultra2"],
    "ae1": ["ae1"],
    "gazelle": ["gazelle"],
    "kiger": ["kiger", "vaporfly", "vaporfly3"],
    "metcon": ["metcon", "speedgoat", "speedgoat5"],
}


def compute_telemetry(category: str) -> dict:
    cat = (category or "").strip()
    if cat == "Running":
        return {"cushion": 94, "response": 96, "traction": 84}
    if cat == "Basketball":
        return {"cushion": 88, "response": 90, "traction": 92}
    if cat == "Trail":
        return {"cushion": 84, "response": 82, "traction": 98}
    return {"cushion": 78, "response": 76, "traction": 85}


@app.route("/media/uploads/<path:filename>")
def uploaded_media(filename: str):
    return send_from_directory(UPLOAD_FOLDER, filename)


def resolve_image_url(image_file: str) -> str:
    clean = (image_file or "").strip()
    stem = os.path.splitext(clean)[0] if clean else "ak"

    if clean:
        if UPLOAD_FOLDER != STATIC_IMAGES_DIR and os.path.isfile(os.path.join(UPLOAD_FOLDER, clean)):
            return url_for("uploaded_media", filename=clean)
        if os.path.isfile(os.path.join(STATIC_IMAGES_DIR, clean)):
            return url_for("static", filename="images/" + clean)

    try:
        available = [
            f
            for f in os.listdir(STATIC_IMAGES_DIR)
            if os.path.splitext(f)[1].lower().lstrip(".") in ALLOWED_EXTENSIONS
        ]
    except OSError:
        available = []

    norm_stem = _norm(stem)
    aliases = KEYWORD_ALIASES.get(norm_stem, [norm_stem])

    for fname in available:
        if _norm(os.path.splitext(fname)[0]) == norm_stem:
            return url_for("static", filename="images/" + fname)

    for alias in aliases:
        if not alias:
            continue
        for fname in available:
            if alias in _norm(os.path.splitext(fname)[0]):
                return url_for("static", filename="images/" + fname)

    return url_for("fallback_sneaker_svg", label=(stem or "AK")[:10])


@app.route("/media/fallback/<label>.svg")
def fallback_sneaker_svg(label: str):
    safe_label = "".join(ch for ch in label if ch.isalnum() or ch in (" ", "-")).upper()[:10] or "AK"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 420" width="640" height="420">
      <rect width="640" height="420" rx="28" fill="#14201B"/>
      <ellipse cx="320" cy="315" rx="210" ry="26" fill="#0A0F0D" opacity="0.7"/>
      <path d="M125 275 C135 235, 175 210, 215 190 L265 132 C282 122, 302 130, 318 156 C355 196, 425 215, 505 232 C522 238, 528 258, 522 278 L125 284 Z"
            fill="#F4F1EA" stroke="#FF4D1C" stroke-width="4"/>
      <path d="M122 278 L525 278 L522 298 L120 298 Z" fill="#FF4D1C"/>
      <text x="320" y="72" text-anchor="middle" fill="#98A39D" font-family="monospace" font-size="18" letter-spacing="4">ATELIER ARCHIVE // {safe_label}</text>
    </svg>"""
    return Response(svg, mimetype="image/svg+xml")


app.jinja_env.globals["resolve_image_url"] = resolve_image_url


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
        "alphafly.jpg",
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
        "samba.jpg",
        "39,40,41,42,43,44",
        18,
        "Low-profile full-grain leather upper with suede T-toe overlay and gum rubber outsole.",
        1,
    ),
    (
        "Terrex Gore-Tex Trail",
        "Outdoor-Style",
        "Trail",
        220.0,
        "ALL-TERRAIN",
        "#16231E",
        "terrex.jpg",
        "40,41,42,43,44,45",
        9,
        "Weather-sealed membrane, rapid lace lock system, and rugged outsole lugs for technical mountain terrain.",
        1,
    ),
    (
        "Adizero Prime X Strung",
        "Adidas-Style",
        "Running",
        230.0,
        "HIGH STACK",
        "#E63E10",
        "adizero.jpg",
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
        "dunk.jpg",
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
        "nb990.jpg",
        "40,41,42,43,44,45",
        11,
        "Pigskin suede and breathable mesh over FuelCell midsole cushioning for all-day architectural comfort.",
        1,
    ),
    (
        "Jordan 1 Court Classic",
        "Jordan-Style",
        "Basketball",
        165.0,
        "COURT ICON",
        "#0D1512",
        "jordan1.jpg",
        "39,40,41,42,43,44",
        15,
        "Structured leather upper, encapsulated heel cushioning, and durable rubber cup-sole traction.",
        0,
    ),
    (
        "Cloudultra 2 Endurance",
        "On-Style",
        "Trail",
        180.0,
        "ULTRA READY",
        "#FF4D1C",
        "cloud.jpg",
        "40,41,42,43,44",
        8,
        "Flip-tongue sock fit, dual-layer superfoam, and high-grip outsole lugs built for endurance miles.",
        0,
    ),
    (
        "AE 1 Low Hardwood",
        "Adidas-Style",
        "Basketball",
        120.0,
        "HARDWOOD",
        "#0D1512",
        "ae1.jpg",
        "40,41,42,43,44,45",
        13,
        "Generative support wing and hybrid midsole cushioning engineered for explosive court cuts.",
        0,
    ),
    (
        "Gazelle Indoor Court",
        "Adidas-Style",
        "Lifestyle",
        125.0,
        "CLASSIC",
        "#16231E",
        "gazelle.jpg",
        "39,40,41,42,43,44",
        16,
        "Supple suede upper, gum sole, and clean terrace proportions inspired by indoor training heritage.",
        0,
    ),
    (
        "Kiger Trail Race",
        "Nike-Style",
        "Trail",
        160.0,
        "TRAIL SPEED",
        "#E63E10",
        "kiger.jpg",
        "40,41,42,43,44",
        6,
        "Lightweight breathable mesh, rock-shield protection, and multi-directional lugs for fast off-road pace.",
        0,
    ),
    (
        "Metcon Training Studio",
        "Reebok-Style",
        "Running",
        155.0,
        "GRIP LAB",
        "#0D1512",
        "metcon.jpg",
        "40,41,42,43,44,45",
        10,
        "Stable heel platform, flexible forefoot, and high-abrasion tread designed for dynamic studio sessions.",
        0,
    ),
]


def init_db() -> None:
    # Migrate existing local store.db if DATA_DIR was newly configured
    legacy_db = os.path.join(BASE_DIR, "store.db")
    if DB_PATH != legacy_db and not os.path.exists(DB_PATH) and os.path.exists(legacy_db):
        shutil.copy2(legacy_db, DB_PATH)

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
    else:
        legacy_to_jpg = {
            "alphafly.png": "alphafly.jpg",
            "samba.png": "samba.jpg",
            "xt6.png": "terrex.jpg",
            "primex.png": "adizero.jpg",
            "dunkhigh.png": "dunk.jpg",
            "990v6.png": "nb990.jpg",
            "kayano31.png": "jordan1.jpg",
            "cloudultra2.png": "cloud.jpg",
            "ae1.png": "ae1.jpg",
            "gazelle.png": "gazelle.jpg",
            "vaporfly3.png": "kiger.jpg",
            "speedgoat5.png": "metcon.jpg",
        }
        for old_name, new_name in legacy_to_jpg.items():
            cur.execute(
                "UPDATE sneakers SET image_file = ? WHERE image_file = ?",
                (new_name, old_name),
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


def get_recent_sneakers(exclude_id: int | None = None, limit: int = 4) -> list[dict]:
    recent_ids = session.get("recently_viewed", [])
    if not recent_ids:
        return []
    conn = get_db()
    result = []
    for sid in recent_ids:
        if exclude_id is not None and int(sid) == int(exclude_id):
            continue
        row = conn.execute("SELECT * FROM sneakers WHERE id = ?", (sid,)).fetchone()
        if row:
            result.append(dict(row))
        if len(result) >= limit:
            break
    conn.close()
    return result


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
    recently_viewed = get_recent_sneakers(limit=4)
    return render_template(
        "shop.html",
        sneakers=filtered,
        categories=categories,
        brands=brands,
        q=q,
        selected_category=category,
        selected_brand=brand,
        sort_by=sort_by,
        recently_viewed=recently_viewed,
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

    rv = [int(x) for x in session.get("recently_viewed", []) if int(x) != sneaker_id]
    rv.insert(0, sneaker_id)
    session["recently_viewed"] = rv[:6]
    session.modified = True

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
    recently_viewed = get_recent_sneakers(exclude_id=sneaker_id, limit=4)
    return render_template(
        "detail.html",
        sneaker=dict(row),
        reviews=reviews,
        avg_rating=avg_rating,
        recently_viewed=recently_viewed,
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


# --- STUDIO ADMIN CONSOLE & PRODUCTION READINESS ---
@app.route("/admin/login", methods=["POST"])
def admin_login():
    pw = (request.form.get("password") or "").strip()
    if not ADMIN_PASSWORD or pw == ADMIN_PASSWORD:
        session["admin_authed"] = True
        session.modified = True
        flash("Studio Admin unlocked.")
    else:
        flash("Invalid Studio Admin passcode.")
    return redirect(url_for("admin_view"))


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin_authed", None)
    session.modified = True
    flash("Studio Admin locked.")
    return redirect(url_for("admin_view"))


@app.route("/admin")
def admin_view():
    if not is_admin_authenticated():
        return render_template("admin.html", locked=True, sneakers=[], orders_count=0)

    conn = get_db()
    sneakers = [dict(r) for r in conn.execute("SELECT * FROM sneakers ORDER BY id DESC").fetchall()]
    orders_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_units = sum(int(s.get("stock") or 0) for s in sneakers)
    catalog_value_usd = sum(float(s.get("price") or 0) * int(s.get("stock") or 0) for s in sneakers)
    conn.close()

    storage_mode = "Persistent Disk" if DATA_DIR != BASE_DIR else "Local Ephemeral Disk"
    return render_template(
        "admin.html",
        locked=False,
        sneakers=sneakers,
        orders_count=orders_count,
        total_units=total_units,
        catalog_value_usd=catalog_value_usd,
        storage_mode=storage_mode,
        data_dir=DATA_DIR,
        admin_protected=bool(ADMIN_PASSWORD),
    )


@app.route("/admin/add", methods=["POST"])
def admin_add():
    if not is_admin_authenticated():
        return redirect(url_for("admin_view"))

    name = (request.form.get("name") or "").strip()
    brand = (request.form.get("brand") or "Atelier").strip()
    category = (request.form.get("category") or "Lifestyle").strip()
    price = float(request.form.get("price") or 150.0)
    stock = max(0, int(request.form.get("stock") or 10))
    badge = (request.form.get("badge") or "NEW DROP").strip()
    sizes = (request.form.get("sizes") or "40,41,42,43,44").strip()
    description = (request.form.get("description") or "").strip()
    featured = 1 if request.form.get("featured") else 0

    image_file = "samba.jpg"
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


@app.route("/admin/edit/<int:sneaker_id>", methods=["POST"])
def admin_edit(sneaker_id: int):
    if not is_admin_authenticated():
        return redirect(url_for("admin_view"))

    price = max(1.0, float(request.form.get("price") or 150.0))
    stock = max(0, int(request.form.get("stock") or 0))
    badge = (request.form.get("badge") or "ARCHIVE").strip()
    sizes = (request.form.get("sizes") or "40,41,42,43,44").strip()
    featured = 1 if request.form.get("featured") else 0

    conn = get_db()
    conn.execute(
        """
        UPDATE sneakers
        SET price = ?, stock = ?, badge = ?, sizes = ?, featured = ?
        WHERE id = ?
        """,
        (price, stock, badge, sizes, featured, sneaker_id),
    )
    conn.commit()
    conn.close()
    flash(f"Updated silhouette #{sneaker_id:02d}.")
    return redirect(url_for("admin_view"))


@app.route("/admin/delete/<int:sneaker_id>", methods=["POST"])
def admin_delete(sneaker_id: int):
    if not is_admin_authenticated():
        return redirect(url_for("admin_view"))

    conn = get_db()
    conn.execute("DELETE FROM sneakers WHERE id = ?", (sneaker_id,))
    conn.commit()
    conn.close()
    flash("Silhouette removed from catalog.")
    return redirect(url_for("admin_view"))


@app.route("/admin/export")
def admin_export():
    if not is_admin_authenticated():
        return redirect(url_for("admin_view"))

    conn = get_db()
    sneakers = [dict(r) for r in conn.execute("SELECT * FROM sneakers ORDER BY id ASC").fetchall()]
    conn.close()
    payload = json.dumps({"exported_at": datetime.utcnow().isoformat(), "sneakers": sneakers}, indent=2)
    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=atelier-kicks-catalog.json"},
    )


@app.route("/admin/import", methods=["POST"])
def admin_import():
    if not is_admin_authenticated():
        return redirect(url_for("admin_view"))

    file = request.files.get("backup_file")
    if not file or not file.filename:
        flash("Please choose a valid catalog JSON backup file.")
        return redirect(url_for("admin_view"))

    try:
        raw = json.loads(file.read().decode("utf-8"))
        items = raw.get("sneakers", raw) if isinstance(raw, dict) else raw
        if not isinstance(items, list) or not items:
            raise ValueError("Empty or invalid catalog structure")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM sneakers")
        for s in items:
            cur.execute(
                """
                INSERT INTO sneakers
                    (name, brand, category, price, badge, accent_hex, image_file, sizes, stock, description, featured)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    s["name"],
                    s.get("brand", "Atelier"),
                    s.get("category", "Lifestyle"),
                    float(s.get("price", 150.0)),
                    s.get("badge", "ARCHIVE"),
                    s.get("accent_hex", "#FF4D1C"),
                    s.get("image_file", "samba.jpg"),
                    s.get("sizes", "40,41,42,43,44"),
                    int(s.get("stock", 10)),
                    s.get("description", ""),
                    int(s.get("featured", 0)),
                ),
            )
        conn.commit()
        conn.close()
        flash(f"Restored {len(items)} silhouettes from JSON backup.")
    except Exception as exc:
        flash(f"Backup restore failed: {exc}")

    return redirect(url_for("admin_view"))


@app.route("/health")
def health_check():
    return jsonify({"status": "ok", "storage": "persistent" if DATA_DIR != BASE_DIR else "local"})


@app.route("/api/catalog")
def api_catalog():
    conn = get_db()
    rows = conn.execute("SELECT * FROM sneakers ORDER BY id ASC").fetchall()
    conn.close()
    items = []
    for r in rows:
        telemetry = compute_telemetry(r["category"])
        items.append(
            {
                "id": r["id"],
                "name": r["name"],
                "brand": r["brand"],
                "category": r["category"],
                "badge": r["badge"],
                "price_raw": r["price"],
                "price_formatted": format_price(r["price"]),
                "image_url": resolve_image_url(r["image_file"]),
                "sizes": [s.strip() for s in r["sizes"].split(",") if s.strip()],
                "description": r["description"],
                "stock": r["stock"],
                "telemetry": telemetry,
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
                "image_url": resolve_image_url(s["image_file"]),
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


@app.route("/api/cart/update/<path:item_key>", methods=["POST"])
def api_cart_update(item_key: str):
    data = request.get_json(silent=True) or {}
    delta = int(data.get("delta", 0))
    cart = session.get("cart", {})
    if item_key in cart:
        new_qty = int(cart[item_key].get("qty", 1)) + delta
        if new_qty <= 0:
            del cart[item_key]
        else:
            cart[item_key]["qty"] = new_qty
        session["cart"] = cart
        session.modified = True
    return api_cart_state()


@app.route("/api/cart/remove/<path:item_key>", methods=["POST"])
def api_cart_remove(item_key: str):
    cart = session.get("cart", {})
    if item_key in cart:
        del cart[item_key]
        session["cart"] = cart
        session.modified = True
    return api_cart_state()


if __name__ == "__main__":
    app.run(debug=True)