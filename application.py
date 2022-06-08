import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # check for empty index
    user_portfolio = "user_" + str(session["user_id"]) + "_portfolio"
    check = db.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name = :user_portfolio", user_portfolio=user_portfolio)
    if check[0]['count(name)'] != 1:
        return render_template("index_blank.html")

    # check if there is transaction data

    table = db.execute("SELECT symbol, number FROM :user_portfolio", user_portfolio=user_portfolio)
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    print(table)

    if table == []:
        return render_template("index.html", table=table, cash=cash)

    else:

        funds = cash[0]["cash"]

        names = [lookup(table[i]["symbol"])["name"] for i in range(len(table))]
        prices = [lookup(table[i]["symbol"])["price"] for i in range(len(table))]
        totals = [table[i]["number"] * lookup(table[i]["symbol"])["price"] for i in range(len(table))]

        for i in range(len(totals)):
            table[i]["name"] = names[i]
            table[i]["price"] = prices[i]
            table[i]["total"] = totals[i]
            funds += totals[i]


        return render_template("index.html", cash=cash, table=table, funds=funds)




@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # call lookup function
        ticker = request.form.get("symbol").upper()
        symbol = lookup(ticker)
        if not symbol:
            return apology("Symbol invalid or not available")

        number = int(request.form.get("shares"))
        if number < 0 or type(number) == str:
            return apology("Invalid number of shares")

        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

        costs = symbol['price'] * number
        if costs > cash[0]['cash']:
            return apology("Not enough cash, stranger!")
        else:
            funds = cash[0]['cash'] - costs
            db.execute("UPDATE users SET cash = :funds WHERE id = :id", funds=funds, id=session["user_id"])

        user_transactions = "user_" + str(session["user_id"]) + "_transactions"
        user_portfolio = "user_" + str(session["user_id"]) + "_portfolio"

        check = db.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name = :user_transactions", user_transactions=user_transactions)

        if check[0]['count(name)'] == 1:
            db.execute("INSERT INTO :user_transactions (symbol, number, price, total) VALUES (:symbol, :number, :price, :total)",
                        user_transactions=user_transactions, symbol=ticker, number=number, price=symbol['price'], total=costs)

            portfolio_value = db.execute("SELECT * FROM :user_portfolio WHERE symbol = :symbol", user_portfolio=user_portfolio, symbol=ticker)
            if portfolio_value != []:
                new_number = portfolio_value[0]["number"] + number
                db.execute("UPDATE :user_portfolio SET number = :new_number WHERE symbol = :symbol", user_portfolio=user_portfolio, new_number=new_number, symbol=ticker)
            else:
                db.execute("INSERT INTO :user_portfolio (symbol, number) VALUES (:symbol, :number)",
                        user_portfolio=user_portfolio, symbol=ticker, number=number)

        else:
            db.execute("CREATE TABLE :user_portfolio (symbol varchar(255), number int)", user_portfolio=user_portfolio)
            db.execute("INSERT INTO :user_portfolio (symbol, number) VALUES (:symbol, :number)",
                        user_portfolio=user_portfolio, symbol=ticker, number=number)

            db.execute("CREATE TABLE :user_transactions (trans_id INTEGER PRIMARY KEY, symbol varchar(255), number int, price money, total money, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)", user_transactions=user_transactions)
            db.execute("INSERT INTO :user_transactions (symbol, number, price, total) VALUES (:symbol, :number, :price, :total)",
                        user_transactions=user_transactions, symbol=ticker, number=number, price=symbol['price'], total=costs)


        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")




@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    user_transactions = "user_" + str(session["user_id"]) + "_transactions"
    transactions = db.execute("SELECT * FROM :user_transactions", user_transactions=user_transactions)
    print(transactions)


    return render_template("history.html", table=transactions)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # call lookup function
        quote = lookup(request.form.get("symbol").upper())
        clicked = True
        if quote == None:
            message = "Symbol invalid or not in database"
            return render_template("quote.html", message=message, clicked=clicked)

        else:
            message = f"A share of {quote['name']} ({quote['symbol']}) costs ${quote['price']}."
            return render_template("quote.html", message=message, clicked=clicked)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure username is not already taken
        elif db.execute("SELECT username FROM users WHERE username = ?", (request.form.get("username"))) != []:
            return apology("username already taken", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Check password confirmation
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password confirmation does not match", 403)

        # create new db entry
        else:
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :pw)", username=request.form.get("username"), pw=generate_password_hash(request.form.get("password")))

        return render_template("login.html")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    user_portfolio = "user_" + str(session["user_id"]) + "_portfolio"
    user_transactions = "user_" + str(session["user_id"]) + "_transactions"
    portfolio = db.execute("SELECT symbol, number FROM :user_portfolio", user_portfolio=user_portfolio)

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        symbol = lookup(request.form.get("symbol"))
        amount = int(request.form.get("shares"))
        print(symbol)
        print(portfolio)
        shares = {}
        for i in portfolio:
            if i["symbol"] == symbol["symbol"]:
                shares = i

        print(shares)

        if amount > shares["number"]:
            return apology("Too many shares")

        new_amount = shares["number"] - amount
        db.execute("UPDATE :user_portfolio SET number = :new_number WHERE symbol = :symbol", user_portfolio=user_portfolio, new_number=new_amount, symbol=symbol["symbol"])

        sell_cash = symbol["price"] * amount
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        total_cash = sell_cash + user_cash[0]["cash"]
        db.execute("UPDATE users SET cash = :total_cash WHERE id = :id", total_cash=total_cash, id=session["user_id"])

        db.execute("INSERT INTO :user_transactions (symbol, number, price, total) VALUES (:symbol, :number, :price, :total)",
                        user_transactions=user_transactions, symbol=symbol["symbol"], number=(-amount), price=symbol['price'], total=sell_cash)


        # remove empties
        db.execute("DELETE FROM :user_portfolio WHERE number = 0", user_portfolio=user_portfolio)


        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:

        return render_template("sell.html", portfolio=portfolio)




def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
