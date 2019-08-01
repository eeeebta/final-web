import os
import requests

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from flask_mail import Mail

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

# Secret key
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

Session(app)

mail = Mail(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

block_title = ["Error", "Success", "Logged out"]

# Possibly another database for this? TODO
common_passwords = []

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    # Taken from CS50 Finance with edits
    user_inp = request.form.get("username")
    user_email = request.form.get("email")
    p1 = request.form.get("password")
    p2 = request.form.get("confirmation")

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not user_inp:
            message = "Username was not provided."
            return render_template("status.html", message=message, block_title=block_title[0]), 400

        # Ensure password was submitted
        elif not p1:
            message = "Password was not provided."
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        
        # If the first and second password do not math then return an error
        elif p1 != p2:
            message = "Passwords do not match."
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        
        # Our district gives us our own emails so it would be preferable
        # to use those emails in order to grant access.
        # Of course during my testing I disabled this.
        # TODO UNCOMMENT
        elif "@cpsd.us" not in user_email:
            message = "Your email is not valid on this website."
            return render_template("status.html", message=message, block_title=block_title[0]), 400

        # So since I only need one username to check its existance this is what I did
        # It returns "None" if nothing is found, but will return a profile if it is not empty
        # This seems to be the equivalent of what CS50 Finance did
        # This was the part that really got me stuck cause I tried to do what CS50 finance did
        # https://stackoverflow.com/questions/18110033/getting-first-row-from-sqlalchemy
        # Originally used .first() for everything but after documentation changed it to .fetchone() just to be consistent
        result = db.execute("SELECT * FROM users WHERE username = :username", {"username": user_inp}).fetchone()

        # If it db.execute to find if username exists returns something then the username exists
        if result:
            message = "Username already exists"
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        elif p1 in common_passwords:
            message = "This password is too common"
            return render_template("status.html", message=message, block_title=block_title[0]), 400

        # Hashed the password and stored it in a variable
        hashed_password = generate_password_hash(p1)
        
        # If everything passed then insert user creds into the table 
        db.execute("INSERT INTO users (username, password) VALUES (:username, :hashed_password)",
         {"username": user_inp, "hashed_password": hashed_password})
        
        # Commit and add data into table
        db.commit()

        # Logs in the user automatically
        session["user_id"] = result

        # Redirect user to home page
        return redirect(url_for("search"))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if session.get("user_id") is not None:
        return redirect(url_for("index"))
    
    # In case someone is able to get through while being logged in
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            message = "You did not enter a password."
            return render_template("status.html", message=message, block_title=block_title[0]), 400

        # Ensure password was submitted
        elif not request.form.get("password"):
            message = "You did not enter a password."
            return render_template("status.html", message=message, block_title=block_title[0]), 400

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", {"username":request.form.get("username")}).fetchone()

        # Ensure username exists and password is correct
        # Had to edit this a little from CS50 Finance because it no longer returns a dictionary but a list
        if not check_password_hash(rows[2], request.form.get("password")):
            message = "Invalid username and/or password."
            return render_template("status.html", message=message, block_title=block_title[0]), 400

        # Remember which user has logged in
        session["user_id"] = rows[0]

        # Redirect user to search page
        return redirect(url_for("search"))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")
    


@app.route("/logout")
def logout():
    # Logs user out
    session.clear()
    message = "Logged out!"
    return render_template("status.html", message=message, block_title=block_title[2])


@login_required
def post():
    user_id = session["user_id"]
    check_super_user = db.execute("SELECT * FROM users WHERE user_id = :user_id", {"user_id":user_id}).fetchone()
    if check_super_user:
        print(check_super_user)


@app.route("/search", methods=["GET", "POST"])
@login_required
def search():

    if request.method == "POST":

        if not request.form.get("query"):
            message = "You did not enter anything in the search box"
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        
        # Thank you Brain!
        q = "%" + request.form.get("query") + "%"
        qf = request.form.get("filter")

        # Searching up documentation is great: https://kite.com/python/docs/sqlalchemy.engine.result.ResultProxy
        # Originally this was split but I decided to make it into one because it allowed me to make the page look nicer
        # Also forgot "OR" statements existed in SQL https://www.w3schools.com/sql/sql_and_or.asp
        # I also had radios as would be seen in the previous commits of this project
        if qf == "isbn":
            qr = db.execute("SELECT * FROM books WHERE isbn LIKE :isbn", {"isbn": q}).fetchall()
        elif qf == "title":
            qr = db.execute("SELECT * FROM books WHERE title LIKE :title", {"title": q}).fetchall()
        elif qf == "auth":
            qr = db.execute("SELECT * FROM books WHERE author LIKE :author", {"author": q}).fetchall()
        elif qf == "py":
            # Not sure if this will be used at all
            qr = db.execute("SELECT * FROM books WHERE year LIKE :year", {"year": q}).fetchall()
        else:
            qr = db.execute("SELECT * FROM books WHERE isbn LIKE :query OR author LIKE :query OR title LIKE :query OR year like :query", {"query": q}).fetchall()

        # If the query result using the filter is not 
        if not qr:
            message = "Your query did not match anything in our databases."
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        return render_template("booklist.html", books=qr)
    else:
        return render_template("search.html")


@app.route("/book/<isbn>", methods=["GET"])
@login_required
def bookpage(isbn):

    # Code from project1 page
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "PklbHNIY4DCcBKaFL3B8qw", "isbns": isbn})
    book = res.json()

    # Returned book info from JSON
    return_book = book["books"][0]

    # Book name and info from database
    book_name = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()

    # How many reviews there are in my database for the specific book
    review_count = db.execute("SELECT COUNT(*) FROM reviews WHERE isbn = :isbn", {"isbn": isbn}).fetchall()

    # This is the real count
    review_count = review_count[0][0]

    # Selects all reviews from database
    reviews = db.execute("SELECT review FROM reviews WHERE isbn = :isbn", {"isbn": isbn}).fetchall()

    # Return the template with all the book information and reviews
    return render_template("bookpage.html", book_name=book_name, book_info=return_book, reviews=reviews, review_count=review_count)

# I assume that no one will be posting to the api
@app.route("/api/<isbn>", methods=["GET"])
def api(isbn):

    # Get the count of reviews
    result = db.execute("SELECT COUNT(*) FROM reviews WHERE isbn = :isbn", {"isbn": isbn}).fetchall()

    # Get book information
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()

    # Check if that isbn is associated with a book
    if not book:
        return jsonify({
            "error": "isbn not found"
            }), 404
    
    # Prepare variables to passed to jsonify
    review_count = result[0][0]
    book_isbn = book[0]
    book_title = book[1]
    book_author = book[2]
    book_year = book[3]

    # I had it return everything like this, however it reorders it. 
    # I assume this jsonify is just reordering the labels alphabetically.
    return jsonify({
        "title": book_title,
        "author": book_author,
        "year": book_year,
        "isbn": book_isbn,
        "review_count": review_count
    })