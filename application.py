import re
import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from helpers import *

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
    # Store the username of the user logged
    user_id=session["user_id"]
    print(user_id)

    stocks=db.execute("SELECT stock ,name, SUM(quantity) as shares , price FROM transactions WHERE user_id=? GROUP BY stock",user_id )
    result = db.execute("SELECT cash FROM users WHERE id=?" , user_id)
    cash = result[0]["cash"]
    total = cash

    for stock in stocks:
        price = lookup(stock['stock'])['price']
        total += stock['shares'] * price

    return render_template("index.html", stocks=stocks , cash=usd(cash) , usd=usd, total=usd(total) )

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if (not request.form.get("symbol")) or (not request.form.get("shares")):
            return apology("must provide stock symbol and number of shares")
        #check if user had asked for proper number of shares
        elif request.form.get("shares") < str(1) :
            return apology("must provide positive number of shares", 400)
        # If symbol searched is invalid, return apology message
        stock = lookup(request.form.get("symbol"))

        # check iF valid stock name provided
        if stock == None:
            return apology("Stock symbol not valid, please try again")
        #checking total price of stocks
        price = int(request.form.get("shares")) *   stock['price']
        result = db.execute("SELECT cash FROM users WHERE id=:user_id", user_id=session["user_id"])
        #check if user had asked for proper number of shares
        if price > result[0]["cash"]:
            return apology("Sorry, you do not have enough cash for the TRANSACTION")
        # updating cash amount in user's database
        db.execute("UPDATE users SET cash=cash-:price WHERE id=:user_id", price=price, user_id=session["user_id"])
        transaction = db.execute("INSERT INTO transactions (user_id, stock , name,quantity,  price,type, date) VALUES (?,?,?,?,?,?,?)",
           session["user_id"], stock["symbol"] ,stock["name"], int(request.form.get("shares")), stock['price'], "buy"
            ,datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id=session["user_id"]
    print(user_id)
    portfolio = db.execute("SELECT stock, type, quantity, price, date FROM transactions WHERE user_id = ?", user_id )

    if not portfolio:
        return apology("Sorry you haven't bought ant stocks yet")

    return render_template("history.html", stocks=portfolio , usd=usd)



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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("please enter a symbol")
        stock= lookup(request.form.get("symbol"))
        # If symbol searched is invalid, return apology message
        if not stock:
            return apology("invalid symbol", 400)
      # If the symbol exists, return the search
        return render_template("quoted.html", name=stock["name"], symbol=stock["symbol"], price=usd(stock["price"]))
    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password=request.form.get("password")
        c_password=request.form.get("confirmation")
        #show apology if some error was occured
        if not username:
            return apology("must provide username",400)
        elif not password or not  c_password :
            return apology("must provide password" ,400)
        #implemented the regex's function with the help  of stackoverflow
        elif len(password) < 8:
            return apology("Make sure your password is at lest 8 letters",400)
        elif re.search('[0-9]',password) is None:
            return apology("Make sure your password has a number in it",400)
        elif re.search('[A-Z]',password) is None:
            return apology("Make sure your password has a capital letter in it",400)
        elif re.search('[!, @ , #, $]',password) is None:
            return apology("Make sure your password has a special character !, @ , #, $ in it",400)

        #MAKE SURE BOTH PASSWORD MATCH
        elif  password !=  c_password:
            return apology("both password  must match", 400)

        # Ensure username is not repeated
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        if len(rows) >= 1:
            return apology("username already exists" , 400)
        # Start session
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",username=request.form.get("username"),
                             hash=generate_password_hash(request.form.get("password")))

        rows = db.execute("SELECT id FROM users WHERE username = username")
        session["user_id"] = rows[0]["id"]
        return redirect("/", 200)
    else:
        return render_template("register.html")




@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id=session["user_id"]
    if request.method == "POST":
        shares=int(request.form.get("shares"))
        stocks=request.form.get("symbol")
        #check if user had asked for positive number of shares
        if shares < 1 :
            return apology("Please enter valid number of shares", 400)
        result = db.execute("SELECT quantity FROM  transactions WHERE stock=? AND  user_id = ?", stocks,user_id )
        print(result)
        #check if user had asked for proper number of shares
        if shares > result[0]['quantity']:
            return apology("Sorry, you do not have enough shares",400)
        # updating cash amount in user's database
        cash=db.execute("SELECT cash FROM users WHERE id=?" , user_id)
        cash=cash[0]["cash"]
        cost=lookup(stocks)["price"]
        price = shares * cost
        db.execute("UPDATE users SET cash= ? WHERE id=?", cash+price ,user_id)
        db.execute("INSERT INTO transactions (user_id, stock , type,quantity, price, date) VALUES (?,?,?,?,?,?)",
            user_id, stocks ,"sell", -shares, cost,datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return redirect("/")
    else:
        Stocks = db.execute("SELECT stock FROM transactions WHERE user_id = ? GROUP BY stock", user_id)
        return render_template("sell.html", stocks=Stocks)

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
