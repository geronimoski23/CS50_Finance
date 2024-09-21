import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    id = session["user_id"]

    portfolio = db.execute(
        "SELECT Symbol, Shares FROM (select Symbol, sum(Shares) as Shares from transactions where userID = ? GROUP BY symbol) WHERE Shares > 0",
        id,
    )

    total = 0

    for n in portfolio:
        details = lookup(n["Symbol"])
        if details is not None:
            n["name"] = details["name"]
            n.update({"price": usd(details["price"])})
            n.update({"total": usd(n["Shares"] * details["price"])})
            total += details["price"] * n["Shares"]

    rows = db.execute("SELECT cash FROM users where id = ?", id)
    cash = float(rows[0]["cash"])
    total += cash
    return render_template(
        "index.html", portfolio=portfolio, total=usd(total), cash=usd(cash)
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        id = session["user_id"]
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        if not symbol:
            return apology("must provide a symbol", 400)
        elif not shares:
            return apology("must provide number of shares", 400)
        else:
            try:
                shares = int(shares)
                if shares <= 0:
                    return apology("must provide positive shares", 400)

            except ValueError:
                return apology("can't buy fractional shares", 400)

        details = lookup(symbol)
        if details is None:
            return apology("Unknown Symbol", 400)

        row = db.execute("SELECT cash FROM users WHERE id = ?", id)
        cash = float(row[0]["cash"])
        price = details["price"]
        transaction_amount = price * shares
        if transaction_amount > cash:
            return apology("Cannot Afford", 400)

        cash = cash - transaction_amount
        db.execute("UPDATE users set cash = ? WHERE id = ?", cash, id)
        db.execute(
            "INSERT INTO transactions VALUES (?,?,?,?, datetime())",
            id,
            symbol,
            shares,
            price,
        )

        flash("Bought!")

        return redirect("/")

        ## check if valid symbol is provided
        ## total = shares * price using quote
        ## get cash amount using index
        ## if total is greater than cash, return error
        ## else
        ## decrease cash amount in users
        ## insert row into transactions
        ## add to users
        ## render template index

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    id = session["user_id"]

    t_history = db.execute("SELECT * from transactions where userID = ?", id)

    return render_template("history.html", t_history=t_history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide a symbol", 400)
        elif lookup(request.form.get("symbol")) is None:
            return apology("must provide a valid symbol")
        else:
            name = lookup(request.form.get("symbol"))["name"]
            symbol = lookup(request.form.get("symbol"))["symbol"]
            price = lookup(request.form.get("symbol"))["price"]
            return render_template(
                "quoted.html", name=name, symbol=symbol, price=usd(price)
            )

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()

    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 400)
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords must match", 400)
        else:
            name = request.form.get("username")
            rows = db.execute("SELECT * FROM users WHERE username = ?", name)
            if len(rows) != 0:
                return apology("user already exists", 400)
            else:
                passwd = request.form.get("password")
                id = db.execute(
                    "INSERT INTO users (username, hash) VALUES (?, ?)",
                    name,
                    generate_password_hash(passwd),
                )
                session["user_id"] = id
                # rows = db.execute("SELECT * FROM users WHERE username = ?", name)
                return redirect("/")
    else:
        return render_template("registration.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    id = session["user_id"]

    portfolio = db.execute(
        "SELECT Symbol, Shares FROM (select Symbol, sum(Shares) as Shares from transactions where userID = ? GROUP BY symbol) WHERE Shares > 0",
        id,
    )

    # create boolean value SellAll
    SellAll = request.form.get("sellall") == "sellall"

    if request.method == "POST":
        shares = request.form.get("shares")
        if SellAll is False and not shares:
            return apology("must provide number of shares", 400)
        elif SellAll is True:
            pass
        else:
            try:
                shares = int(shares)
            except ValueError:
                return apology("can't sell fractional shares", 400)

        ## if there are not enough shares in portfolio, return apology
        symbol = request.form.get("symbol")
        print(symbol)
        details = lookup(symbol)
        for s in portfolio:
            if symbol == s["Symbol"]:
                num_shares = s["Shares"]
                price = details["price"]

        ## if there are, update number of shares in transaction

        if SellAll is False:
            if shares > num_shares:
                return apology("You do not have enough shares", 400)
            else:
                db.execute(
                    "INSERT INTO transactions VALUES (?,?,?,?, datetime())",
                    id,
                    symbol,
                    0 - shares,
                    price,
                )
        else:
            shares = num_shares
            db.execute(
                "INSERT INTO transactions VALUES (?,?,?,?, datetime())",
                id,
                symbol,
                0 - shares,
                price,
            )

        flash("Sold!")

        rows = db.execute("SELECT cash FROM users where id = ?", id)
        cash = float(rows[0]["cash"])
        sale_total = shares * price
        cash = cash + sale_total
        db.execute("UPDATE users set cash = ? WHERE id = ?", cash, id)
        return redirect("/")
    return render_template("sell.html", portfolio=portfolio)


@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    id = session["user_id"]

    add = request.form.get("add")

    if request.method == "POST":
        if not add:
            return apology("must provide amount of cash", 400)
        else:
            try:
                float_cash = float(add)
            except ValueError:
                return apology("must provide cash amount", 400)
        flash("Cash Added!")

        rows = db.execute("SELECT cash FROM users where id = ?", id)
        user_cash = float(rows[0]["cash"])
        user_cash = user_cash + float_cash
        print(user_cash)
        db.execute("UPDATE users set cash = ? WHERE id = ?", user_cash, id)
        return redirect("/")
    else:
        # For "GET"
        return render_template("addcash.html")
