import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
import pymysql.cursors

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# --- Database connection settings (read from environment variables) ---
# In production (EC2/RDS) these come from environment variables set in
# the Docker container or ECS/EC2 task definition. Locally, defaults are used.
DB_HOST = os.environ.get("DB_HOST", "restaurant-db.cry2eu46qsyp.ap-southeast-2.rds.amazonaws.com")
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Sireeshamanku")
DB_NAME = os.environ.get("DB_NAME", "restaurant_db")


def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
    )


# ---------------------------------------------------------------------
# Public / Customer routes
# ---------------------------------------------------------------------

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/menu")
def menu():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM menu_items ORDER BY category, name")
            items = cursor.fetchall()
    finally:
        conn.close()
    return render_template("menu.html", items=items)


@app.route("/add_to_cart/<int:item_id>", methods=["POST"])
def add_to_cart(item_id):
    if "cart" not in session:
        session["cart"] = {}

    cart = session["cart"]
    item_id_str = str(item_id)
    cart[item_id_str] = cart.get(item_id_str, 0) + 1
    session["cart"] = cart
    flash("Item added to cart!")
    return redirect(url_for("menu"))


@app.route("/cart")
def view_cart():
    cart = session.get("cart", {})
    items = []
    total = 0

    if cart:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                ids = tuple(int(i) for i in cart.keys())
                format_strings = ",".join(["%s"] * len(ids))
                cursor.execute(
                    f"SELECT * FROM menu_items WHERE id IN ({format_strings})", ids
                )
                rows = cursor.fetchall()
                for row in rows:
                    qty = cart[str(row["id"])]
                    subtotal = float(row["price"]) * qty
                    total += subtotal
                    items.append({**row, "qty": qty, "subtotal": subtotal})
        finally:
            conn.close()

    return render_template("cart.html", items=items, total=total)


@app.route("/place_order", methods=["POST"])
def place_order():
    if "user_id" not in session:
        flash("Please log in to place an order.")
        return redirect(url_for("login"))

    cart = session.get("cart", {})
    if not cart:
        flash("Your cart is empty.")
        return redirect(url_for("menu"))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO orders (user_id, status) VALUES (%s, %s)",
                (session["user_id"], "pending"),
            )
            order_id = cursor.lastrowid

            for item_id, qty in cart.items():
                cursor.execute(
                    "INSERT INTO order_items (order_id, menu_item_id, quantity) "
                    "VALUES (%s, %s, %s)",
                    (order_id, int(item_id), qty),
                )
        conn.commit()
    finally:
        conn.close()

    session["cart"] = {}
    flash("Order placed successfully!")
    return redirect(url_for("order_status", order_id=order_id))


@app.route("/order/<int:order_id>")
def order_status(order_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
    finally:
        conn.close()
    return render_template("order_status.html", order=order)


# ---------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed = generate_password_hash(password)

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                    (username, hashed, "customer"),
                )
            conn.commit()
        finally:
            conn.close()

        flash("Registration successful. Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()
        finally:
            conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash("Logged in successfully.")
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("home"))

        flash("Invalid username or password.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("home"))


# ---------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------

def admin_required():
    return session.get("role") == "admin"


@app.route("/admin")
def admin_dashboard():
    if not admin_required():
        flash("Admin access only.")
        return redirect(url_for("login"))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT o.id, o.status, o.created_at, u.username "
                "FROM orders o JOIN users u ON o.user_id = u.id "
                "ORDER BY o.created_at DESC"
            )
            orders = cursor.fetchall()
    finally:
        conn.close()

    return render_template("admin_dashboard.html", orders=orders)


@app.route("/admin/menu", methods=["GET", "POST"])
def admin_menu():
    if not admin_required():
        flash("Admin access only.")
        return redirect(url_for("login"))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if request.method == "POST":
                name = request.form["name"]
                category = request.form["category"]
                price = request.form["price"]
                cursor.execute(
                    "INSERT INTO menu_items (name, category, price) VALUES (%s, %s, %s)",
                    (name, category, price),
                )
                conn.commit()
                flash("Menu item added.")

            cursor.execute("SELECT * FROM menu_items ORDER BY category, name")
            items = cursor.fetchall()
    finally:
        conn.close()

    return render_template("admin_menu.html", items=items)


@app.route("/admin/menu/delete/<int:item_id>", methods=["POST"])
def delete_menu_item(item_id):
    if not admin_required():
        flash("Admin access only.")
        return redirect(url_for("login"))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM menu_items WHERE id = %s", (item_id,))
        conn.commit()
    finally:
        conn.close()

    flash("Menu item deleted.")
    return redirect(url_for("admin_menu"))


@app.route("/admin/order/<int:order_id>/status", methods=["POST"])
def update_order_status(order_id):
    if not admin_required():
        flash("Admin access only.")
        return redirect(url_for("login"))

    new_status = request.form["status"]
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE orders SET status = %s WHERE id = %s", (new_status, order_id)
            )
        conn.commit()
    finally:
        conn.close()

    flash("Order status updated.")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------
# Health check endpoint - used by the Load Balancer target group
# ---------------------------------------------------------------------

@app.route("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
