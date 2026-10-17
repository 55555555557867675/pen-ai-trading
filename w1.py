
import os
import sqlite3
import random
import time
from functools import wraps
from flask import (
    Flask, request, redirect, url_for,
    session, render_template_string, jsonify, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
csrf = CSRFProtect(app)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("RENDER") == "true"
)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or "local-development-only-key",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("APP_ENV") == "production"
)
DB = "pen_ai_trading.db"

COINS = {
    "BTC": {"name": "Bitcoin", "price": 67500.0},
    "ETH": {"name": "Ethereum", "price": 3500.0},
    "SOL": {"name": "Solana", "price": 150.0},
}


def connect_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                cash REAL NOT NULL DEFAULT 10000
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS holdings (
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, symbol)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


init_db()


def page(title, body):
    body = render_template_string(body)
    return render_template_string("""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{{ title }} | PEN AI Trading</title>
      <style>
        *{box-sizing:border-box}
        body{margin:0;background:#0b1020;color:#e8edf8;font-family:Arial,sans-serif}
        nav{display:flex;justify-content:space-between;align-items:center;gap:12px;
            flex-wrap:wrap;padding:18px 6%;background:#111a2e;border-bottom:1px solid #26324b}
        nav a{color:#d8e3f7;text-decoration:none;margin:0 8px}
        .brand{font-size:22px;font-weight:bold;color:#52e0a1}
        main{max-width:1100px;margin:30px auto;padding:0 18px}
        .card{background:#121b2e;border:1px solid #263550;border-radius:14px;
              padding:22px;margin-bottom:18px}
        .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px}
        h1,h2,h3{margin-top:0}
        .muted{color:#9eabc4}
        .green{color:#52e0a1}.red{color:#ff667d}
        input,select,button{font:inherit;padding:12px;border-radius:8px;border:1px solid #34415c}
        input,select{width:100%;background:#0b1222;color:white;margin:7px 0 14px}
        button,.btn{background:#52e0a1;color:#07130e;font-weight:bold;border:0;
                    cursor:pointer;text-decoration:none;display:inline-block;padding:12px 16px;border-radius:8px}
        .secondary{background:#263550;color:#fff}
        table{width:100%;border-collapse:collapse}
        th,td{text-align:left;padding:12px 8px;border-bottom:1px solid #263550}
        .scroll{overflow-x:auto}
        .hero{padding:50px 0}
        .hero h1{font-size:clamp(32px,6vw,56px)}
        footer{text-align:center;padding:25px;color:#8492ad}
        canvas{width:100%;height:340px;display:block;background:#0b1222;border-radius:8px}
        .notice{padding:12px;background:#1a2940;border-radius:8px;margin-bottom:15px}
        @media(max-width:500px){nav{padding:14px}main{margin:20px auto}}
      </style>
    </head>
    <body>
      <nav>
        <a class="brand" href="/">PEN AI Trading</a>
        <div>
          <a href="/">Home</a>
          {% if session.get('user_id') %}
            <a href="/dashboard">Dashboard</a>
            <a href="/market">Market</a>
            <a href="/chart">Candles</a>
            <a href="/logout">Logout</a>
          {% else %}
            <a href="/login">Login</a>
            <a href="/signup">Sign up</a>
          {% endif %}
        </div>
      </nav>
      <main>{{ body|safe }}</main>
      <footer>Made by Faizan | AI Code by Pen AI · Demo trading only</footer>
    </body>
    </html>
    """, title=title, body=body)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def current_user():
    with connect_db() as con:
        return con.execute(
            "SELECT * FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()


@app.route("/")
def home():
    body = """
    <section class="hero">
      <p class="green">YOUR CRYPTO DEMO PLATFORM</p>
      <h1>Trade smarter with<br><span class="green">PEN AI Trading</span></h1>
      <p class="muted">Explore a demo crypto dashboard, view candlestick charts,
      and practise buying or selling with virtual money.</p>
      <p><a class="btn" href="/signup">Get Started</a>
      <a class="btn secondary" href="/market">Explore Market</a></p>
    </section>
    <div class="grid">
      <div class="card"><h3>Live-style Chart</h3><p class="muted">Moving simulated green and red candles.</p></div>
      <div class="card"><h3>Virtual Portfolio</h3><p class="muted">$10,000 demo balance for new accounts.</p></div>
      <div class="card"><h3>Trade Practice</h3><p class="muted">Try demo buy and sell orders without real money.</p></div>
    </div>
    <p class="muted">All prices and trades on this demo site are simulated, not real market data.</p>
    """
    return page("Home", body)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 6:
            flash("Username must be 3+ characters and password 6+ characters.")
        else:
            try:
                with connect_db() as con:
                    con.execute(
                        "INSERT INTO users(username,password,cash) VALUES(?,?,10000)",
                        (username, generate_password_hash(password))
                    )
                    user = con.execute(
                        "SELECT id FROM users WHERE username=?", (username,)
                    ).fetchone()
                session["user_id"] = user["id"]
                session["username"] = username
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                flash("That username already exists.")
    body = """
    <div class="card" style="max-width:480px;margin:auto">
      <h2>Create account</h2>
      {% with messages = get_flashed_messages() %}
        {% for message in messages %}<div class="notice">{{ message }}</div>{% endfor %}
      {% endwith %}
      <form method="post">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <label>Username</label><input name="username" minlength="3" required>
        <label>Password (at least 6 characters)</label>
        <input type="password" name="password" minlength="6" required>
        <button type="submit">Create Account</button>
      </form>
      <p class="muted">Already registered? <a href="/login">Login</a></p>
    </div>
    """
    return page("Sign up", body)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with connect_db() as con:
            user = con.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()
        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.")
    body = """
    <div class="card" style="max-width:480px;margin:auto">
      <h2>Welcome back</h2>
     {% with messages = get_flashed_messages() %}
  {% for message in messages %}
    <div class="notice">{{ message }}</div>
  {% endwith %}
{% endwith %}
      <form method="post">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <label>Username</label><input name="username" required>
        <label>Password</label><input type="password" name="password" required>
        <button type="submit">Login</button>
      </form>
      <p class="muted">No account? <a href="/signup">Sign up</a></p>
    </div>
    """
    return page("Login", body)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/market")
def market():
    rows = ""
    for symbol, coin in COINS.items():
        rows += (
            "<tr><td><b>" + symbol + "</b></td><td>" + coin["name"] +
            "</td><td class='green'>$" + format(coin["price"], ",.2f") +
            "</td><td><a href='/chart?coin=" + symbol +
            "'>View chart</a></td></tr>"
        )
    body = """
    <h1>Crypto Market</h1>
    <p class="muted">Illustrative prices only — these are not live exchange quotes.</p>
    <div class="card scroll"><table>
      <tr><th>Symbol</th><th>Asset</th><th>Demo Price</th><th>Chart</th></tr>
      """ + rows + """
    </table></div>
    <a class="btn" href="/dashboard">Open Dashboard</a>
    """
    return page("Market", body)


@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    user_id = session["user_id"]
    message = ""

    if request.method == "POST":
        symbol = request.form.get("symbol", "")
        side = request.form.get("side", "")
        try:
            quantity = float(request.form.get("quantity", "0"))
        except ValueError:
            quantity = 0

        if symbol not in COINS or side not in ("BUY", "SELL") or quantity <= 0:
            message = "Enter a valid coin and quantity."
        else:
            price = COINS[symbol]["price"]
            cost = price * quantity
            with connect_db() as con:
                holding = con.execute(
                    "SELECT quantity FROM holdings WHERE user_id=? AND symbol=?",
                    (user_id, symbol)
                ).fetchone()
                held = holding["quantity"] if holding else 0
                cash = con.execute(
                    "SELECT cash FROM users WHERE id=?", (user_id,)
                ).fetchone()["cash"]

                if side == "BUY" and cost > cash:
                    message = "Not enough virtual cash for this demo purchase."
                elif side == "SELL" and quantity > held:
                    message = "You do not have enough of this coin to sell."
                else:
                    if side == "BUY":
                        con.execute("UPDATE users SET cash=cash-? WHERE id=?", (cost, user_id))
                        new_held = held + quantity
                    else:
                        con.execute("UPDATE users SET cash=cash+? WHERE id=?", (cost, user_id))
                        new_held = held - quantity

                    con.execute("""
                        INSERT INTO holdings(user_id,symbol,quantity) VALUES(?,?,?)
                        ON CONFLICT(user_id,symbol) DO UPDATE SET quantity=excluded.quantity
                    """, (user_id, symbol, new_held))
                    con.execute("""
                        INSERT INTO trades(user_id,symbol,side,quantity,price)
                        VALUES(?,?,?,?,?)
                    """, (user_id, symbol, side, quantity, price))
                    message = side + " demo order completed."

    with connect_db() as con:
        user = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        holdings = con.execute(
            "SELECT * FROM holdings WHERE user_id=? AND quantity>0 ORDER BY symbol",
            (user_id,)
        ).fetchall()
        trades = con.execute(
            "SELECT * FROM trades WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (user_id,)
        ).fetchall()

    portfolio_value = sum(h["quantity"] * COINS[h["symbol"]]["price"] for h in holdings)
    total_value = user["cash"] + portfolio_value

    holding_rows = ""
    for h in holdings:
        value = h["quantity"] * COINS[h["symbol"]]["price"]
        holding_rows += (
            "<tr><td>" + h["symbol"] + "</td><td>" +
            format(h["quantity"], ".6f") + "</td><td>$" +
            format(value, ",.2f") + "</td></tr>"
        )
    if not holding_rows:
        holding_rows = "<tr><td colspan='3'>No holdings yet.</td></tr>"

    trade_rows = ""
    for t in trades:
        cls = "green" if t["side"] == "BUY" else "red"
        trade_rows += (
            "<tr><td>" + t["created_at"] + "</td><td>" + t["symbol"] +
            "</td><td class='" + cls + "'>" + t["side"] +
            "</td><td>" + format(t["quantity"], ".6f") +
            "</td><td>$" + format(t["price"], ",.2f") + "</td></tr>"
        )
    if not trade_rows:
        trade_rows = "<tr><td colspan='5'>No demo trades yet.</td></tr>"

    coin_options = "".join(
        "<option value='" + s + "'>" + s + " — " + c["name"] + "</option>"
        for s, c in COINS.items()
    )
    safe_username = str(session.get("username", "Trader")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    body = """
    <h1>Welcome, """ + safe_username + """</h1>
    <p class="muted">Your demo trading dashboard</p>
    """ + (("<div class='notice'>" + message + "</div>") if message else "") + """
    <div class="grid">
      <div class="card"><p class="muted">Virtual Cash</p><h2 class="green">$""" + format(user["cash"], ",.2f") + """</h2></div>
      <div class="card"><p class="muted">Holdings Value</p><h2>$""" + format(portfolio_value, ",.2f") + """</h2></div>
      <div class="card"><p class="muted">Total Demo Portfolio</p><h2>$""" + format(total_value, ",.2f") + """</h2></div>
    </div>
    <div class="grid">
      <div class="card">
        <h2>Place a Demo Trade</h2>
        <form method="post">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
          <label>Coin</label><select name="symbol">""" + coin_options + """</select>
          <label>Quantity</label><input type="number" name="quantity" min="0.000001" step="any" required>
          <label>Action</label><select name="side"><option value="BUY">Buy</option><option value="SELL">Sell</option></select>
          <button type="submit">Place Demo Order</button>
        </form>
      </div>
      <div class="card">
        <h2>Market Shortcuts</h2>
        <p><a class="btn" href="/chart">Open Candlestick Chart</a></p>
        <p><a class="btn secondary" href="/market">View Market</a></p>
        <p class="muted">Demo prices may change when the server restarts.</p>
      </div>
    </div>
    <div class="card scroll"><h2>Your Holdings</h2><table>
      <tr><th>Coin</th><th>Quantity</th><th>Demo Value</th></tr>
      """ + holding_rows + """
    </table></div>
    <div class="card scroll"><h2>Recent Trades</h2><table>
      <tr><th>Date</th><th>Coin</th><th>Side</th><th>Quantity</th><th>Price</th></tr>
      """ + trade_rows + """
    </table></div>
    """
    return page("Dashboard", body)


@app.route("/api/candles")
def api_candles():
    symbol = request.args.get("coin", "BTC").upper()
    if symbol not in COINS:
        symbol = "BTC"

    try:
        count = min(max(int(request.args.get("count", 50)), 10), 100)
    except ValueError:
        count = 50

    price = COINS[symbol]["price"]
    candles = []
    start = price * 0.96
    now = int(time.time())

    for i in range(count):
        open_price = start
        close_price = max(0.01, open_price * (1 + random.uniform(-0.008, 0.008)))
        high = max(open_price, close_price) * (1 + random.uniform(0, 0.004))
        low = min(open_price, close_price) * (1 - random.uniform(0, 0.004))
        candles.append({
            "time": now - (count - i) * 60,
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close_price, 2),
            "volume": random.randint(100, 2000)
        })
        start = close_price

    return jsonify({"symbol": symbol, "candles": candles})


@app.route("/chart")
def chart():
    selected = request.args.get("coin", "BTC").upper()
    if selected not in COINS:
        selected = "BTC"

    body = """
    <h1>Candlestick Chart</h1>
    <p class="muted">Green candles indicate a rising candle; red candles indicate a falling candle.
    This chart is simulated, not live exchange data.</p>
    <div class="card">
      <div class="grid">
        <div><label>Asset</label>
          <select id="coin">
            <option value="BTC">BTC — Bitcoin</option>
            <option value="ETH">ETH — Ethereum</option>
            <option value="SOL">SOL — Solana</option>
          </select>
        </div>
        <div><label>Update speed</label>
          <select id="speed">
            <option value="3000">3 seconds</option>
            <option value="5000">5 seconds</option>
            <option value="10000">10 seconds</option>
          </select>
        </div>
      </div>
      <h2 id="chartTitle">BTC / USD</h2>
      <canvas id="chartCanvas" width="1000" height="400"></canvas>
      <p id="status" class="muted">Starting demo candles…</p>
      <button id="pauseBtn" type="button" class="secondary">Pause</button>
      <button id="resumeBtn" type="button">Resume</button>
    </div>
    <script>
    const canvas = document.getElementById("chartCanvas");
    const ctx = canvas.getContext("2d");
    const coinSelect = document.getElementById("coin");
    const speedSelect = document.getElementById("speed");
    const statusText = document.getElementById("status");
    let candles = [];
    let timer = null;
    let paused = false;

    function basePrice() {
      return {BTC:67500, ETH:3500, SOL:150}[coinSelect.value];
    }

    function makeCandle(previous) {
      const open = previous;
      const close = Math.max(0.01, open * (1 + (Math.random()-0.5)*0.012));
      return {
        open: open,
        close: close,
        high: Math.max(open,close)*(1+Math.random()*0.004),
        low: Math.min(open,close)*(1-Math.random()*0.004),
        volume: 100+Math.random()*1900
      };
    }

    function initCandles() {
      candles = [];
      let p = basePrice()*0.96;
      for(let i=0;i<45;i++){
        const c=makeCandle(p);
        candles.push(c);
        p=c.close;
      }
      draw();
    }

    function draw() {
      const w=canvas.width, h=canvas.height;
      ctx.clearRect(0,0,w,h);
      ctx.fillStyle="#0b1222";
      ctx.fillRect(0,0,w,h);

      const pad=55, top=25, bottom=65;
      const chartH=h-top-bottom;
      const values=candles.flatMap(c=>[c.high,c.low]);
      const min=Math.min(...values), max=Math.max(...values);
      const range=(max-min)||1;
      const y=v=>top+(max-v)/range*chartH;
      ctx.font="12px Arial";
      ctx.strokeStyle="#263550";
      ctx.fillStyle="#aab8d0";

      for(let i=0;i<5;i++){
        const yy=top+i*chartH/4;
        ctx.beginPath();ctx.moveTo(pad,yy);ctx.lineTo(w-10,yy);ctx.stroke();
        const price=max-i*range/4;
        ctx.fillText(price.toFixed(2),5,yy+4);
      }

      const slot=(w-pad-15)/candles.length;
      candles.forEach((c,i)=>{
        const x=pad+i*slot+slot/2;
        const rising=c.close>=c.open;
        const color=rising?"#52e0a1":"#ff667d";
        ctx.strokeStyle=color;ctx.fillStyle=color;
        ctx.beginPath();ctx.moveTo(x,y(c.high));ctx.lineTo(x,y(c.low));ctx.stroke();
        const candleTop=y(Math.max(c.open,c.close));
        const candleBottom=y(Math.min(c.open,c.close));
        ctx.fillRect(x-slot*0.3,candleTop,Math.max(2,slot*0.6),Math.max(1,candleBottom-candleTop));
      });

      ctx.fillStyle="#9eabc4";
      ctx.fillText("Older",pad,h-22);
      ctx.fillText("Latest",w-55,h-22);
      const last=candles[candles.length-1];
      statusText.textContent=coinSelect.value+" simulated price: $"+
        last.close.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
    }

    function tick() {
      if(paused)return;
      const last=candles[candles.length-1].close;
      candles.push(makeCandle(last));
      if(candles.length>45)candles.shift();
      draw();
    }

    function restartTimer() {
      if(timer)clearInterval(timer);
      timer=setInterval(tick,Number(speedSelect.value));
    }

    coinSelect.value=""" + repr(selected) + """;
    coinSelect.addEventListener("change",()=>{initCandles();});
    speedSelect.addEventListener("change",restartTimer);
    document.getElementById("pauseBtn").addEventListener("click",()=>{
      paused=true;statusText.textContent="Chart paused.";
    });
    document.getElementById("resumeBtn").addEventListener("click",()=>{
      paused=false;draw();
    });
    initCandles();
    restartTimer();
    </script>
    """
    return page("Candlestick Chart", body)


if __name__ == "__main__":
  if __name__ == "__main__":
    app.run(debug=False)
