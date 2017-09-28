from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    my_dict = {}
    user_list = db.execute("SELECT username, cash from users WHERE id = :user_id", user_id = session['user_id'])
    user_name = user_list[0]['username']
    r_cash = user_list[0]['cash']
    r_cash = float("{0:.2f}".format(r_cash))
    transaction_list = db.execute("SELECT * from 'transaction' WHERE user_name = :user_name", user_name = user_name)
    for each_transaction in transaction_list:
        stock_symbol = each_transaction['stock_symbol']
        stock_amount = each_transaction['quantity']
        stock_price = each_transaction['stock_price']
        if stock_symbol in my_dict:
            my_dict[stock_symbol] += stock_amount
        else:
            my_dict[stock_symbol] = stock_amount
    b_my_list = sorted(my_dict.items())
    my_list = []
    price_list = []
    for item in b_my_list:
        if item[1] != 0:
            my_list.append(item)
            quote = lookup(item[0])
            cur_price = quote['price']
            price_list.append(cur_price)
        
    each_holding = []
    my_list_length = len(my_list)
    for i in range(my_list_length):
        total_price = my_list[i][1] * price_list[i]
        total_price = float("{0:.2f}".format(total_price))
        each_holding.append(total_price)
    
    total_asset = r_cash + sum(each_holding)
    total_asset = float("{0:.2f}".format(total_asset))
    
        
    return render_template('info.html', the_list = my_list, price_list = price_list, each_holding = each_holding, \
                            r_cash = r_cash, total_asset = total_asset)
        

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == 'GET':
        return render_template('purchase.html')
    if request.method == 'POST':
        user_name_list = db.execute("SELECT username from users WHERE id = :user_id", user_id = session['user_id'])
        user_name = user_name_list[0]['username']
        stock_symbol = request.form.get('stock_name')
        stock_symbol = stock_symbol.upper()
        stock_amount = float(request.form.get('amount'))
        stock_amount = int(stock_amount)
        quote = lookup(stock_symbol)
        if quote == None:
            return apology('Incorrect stock symbol name.')
        if stock_amount <= 0:
            return apology('The quantity should be at least one')
        stock_price = quote['price']
        needed_money = stock_price * stock_amount
        cash_list = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session['user_id'])
        have_cash = cash_list[0]['cash']
        if needed_money > have_cash:
            return apology('You do not have enough money for this transaction')
        db.execute("INSERT INTO 'transaction' (user_name, stock_symbol, stock_price, quantity) VALUES(:user_name, :stock_symbol, :stock_price, \
                    :quantity)",user_name = user_name, stock_symbol = stock_symbol, stock_price = stock_price, quantity = stock_amount)
        db.execute("UPDATE users SET cash = :new_cash WHERE id = :user_id", new_cash = have_cash - needed_money, user_id = session['user_id'])
        return redirect(url_for('index'))
                    

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    a_list = db.execute("SELECT username, cash from users WHERE id =:user_id", user_id = session['user_id'])
    user_name = a_list[0]['username']
    user_cash = a_list[0]['cash']
    user_cash = float("{0:.2f}".format(user_cash))
    total_asset = 0
    b_list = db.execute("SELECT stock_symbol, stock_price, quantity, transaction_time from 'transaction' WHERE \
                user_name = :user_name", user_name = user_name )
    for b in b_list:
        total_asset += b['stock_price'] * b['quantity']
    total_asset = float("{0:.2f}".format(total_asset)) + user_cash
    return render_template('history.html', b_list = b_list, r_cash = user_cash, total_asset = total_asset)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == 'GET':
        return render_template("quote.html")
    if request.method == 'POST':
        stock_name = request.form.get('stock_symbol')
        if stock_name == '':
            return apology('You need to input a stock name.')
        quote = lookup(stock_name)
        if quote == None:
            return apology('Incorrect stock name.')
        return render_template('quoted.html', stock_name = quote['name'], stock_symbol = quote['symbol'], stock_price = quote['price'])
        

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    if request.method == 'POST':
        user_name = request.form.get('username')
        user_psw = request.form.get('password')
        user_c_psw = request.form.get('c_password')
        if ((user_name == '') or (user_psw == '') or (user_c_psw == '')):
            return apology("Fill in all the blank boxes please.")
        if user_psw != user_c_psw:
            return apology("Please reconfirm your password.")
        encrypt_psw = pwd_context.encrypt(user_psw)
        registrants = db.execute ("SELECT * FROM users")
        for registrant in registrants:
            if registrant['username'] == user_name:
                return apology("Sorry, this username already exists.")
        db.execute("INSERT INTO users (username, hash) VALUES(:username, :encrypt_psw)", username = user_name, encrypt_psw = encrypt_psw)
        cur_user = db.execute("SELECT * FROM users WHERE username = :username", username = user_name)
        cur_user_id = cur_user[0]['id']
        session["user_id"] = cur_user_id
        return redirect(url_for('index'))
        
        
    if request.method == 'GET':
        return render_template("register.html")
        
@app.route("/resetpw", methods = ["GET", "POST"])
@login_required
def resetpw():
    if request.method == 'GET':
        return render_template('resetpw.html')
    if request.method == 'POST':
        user_list = db.execute("SELECT hash from users WHERE id = :user_id", user_id = session['user_id'])
        user_hash = user_list[0]['hash']
        insert_pw = request.form.get('old_pw')
        true_or_false = pwd_context.verify(insert_pw, user_hash)
        if not true_or_false:
            return apology("Wrong old password. Try again.")
        new_pw = request.form.get('new_pw')
        cn_pw = request.form.get('cn_pw')
        if new_pw != cn_pw:
            return apology("reconfirm your new password!")
        new_hash = pwd_context.encrypt(new_pw)
        db.execute("UPDATE users SET hash = :new_hash WHERE id = :user_id", new_hash = new_hash, user_id = session['user_id'])
        return ('Reset password successfully!')
        
        
        
    

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    my_dict = {}
    user_list = db.execute("SELECT username, cash from users WHERE id = :user_id", user_id = session['user_id'])
    user_name = user_list[0]['username']
    r_cash = user_list[0]['cash']
    r_cash = float("{0:.2f}".format(r_cash))
    transaction_list = db.execute("SELECT * from 'transaction' WHERE user_name = :user_name", user_name = user_name)
    for each_transaction in transaction_list:
        stock_symbol = each_transaction['stock_symbol']
        stock_amount = each_transaction['quantity']
        stock_price = each_transaction['stock_price']
        if stock_symbol in my_dict:
            my_dict[stock_symbol] += stock_amount
        else:
            my_dict[stock_symbol] = stock_amount
    b_my_list = sorted(my_dict.items())
    my_list = []
    price_list = []
    for item in b_my_list:
        if item[1] != 0:
            my_list.append(item)
            quote = lookup(item[0])
            cur_price = quote['price']
            price_list.append(cur_price)
        
    each_holding = []
    my_list_length = len(my_list)
    for i in range(my_list_length):
        total_price = my_list[i][1] * price_list[i]
        total_price = float("{0:.2f}".format(total_price))
        each_holding.append(total_price)
    total_asset = r_cash + sum(each_holding)
    total_asset = float("{0:.2f}".format(total_asset))
    if request.method == 'GET':
        return render_template('sell.html', the_list = my_list, price_list = price_list, each_holding = each_holding, \
                                r_cash = r_cash, total_asset = total_asset)
    if request.method == 'POST':
        sell_name = request.form.get('stock_symbol')
        sell_name = sell_name.upper()
        sell_quantity = float(request.form.get('quantity'))
        sell_quantity = int(sell_quantity)
        if sell_quantity <= 0:
            return apology("sorry, this is invalid amount.")
        if sell_name in my_dict:
            if sell_quantity > my_dict[sell_name]:
                return apology("Exceeding the maximum amount you own")
            minus_amount = 0 - sell_quantity
            quote = lookup(sell_name)
            cur_price = quote['price']
            earnings = sell_quantity * cur_price
            n_cash = r_cash + earnings
            db.execute("INSERT INTO 'transaction' (user_name, stock_symbol, stock_price, quantity) VALUES(:user_name, :stock_symbol, :stock_price, \
                        :quantity)",user_name = user_name, stock_symbol = sell_name, stock_price = cur_price, quantity = minus_amount)
            db.execute("UPDATE 'users' SET cash = :n_cash WHERE id = :user_id", n_cash = n_cash, user_id = session['user_id'])
            return redirect(url_for('index'))
            
        else:
            return apology('You do not own such stock.')