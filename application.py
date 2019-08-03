import os
import requests
import datetime

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for, jsonify
from flask_session import Session
from flask_mail import Mail

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# https://stackoverflow.com/questions/37901716/flask-uploads-ioerror-errno-2-no-such-file-or-directory
from os.path import join, dirname, realpath

from helpers import login_required

# https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/

UPLOAD_FOLDER = join(dirname(realpath(__file__)), "static/images/")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

# Secret key
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

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

    for num in range(10):
        print(db.execute("SELECT * FROM users").fetchall())

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
        elif not user_email:
            message = "Email not provided"
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        elif "@" not in user_email or (".com" or ".net") not in user_email:
            message = "Not a valid email"
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        # Our district gives us our own emails so it would be preferable
        # to use those emails in order to grant access.
        # Of course during my testing I disabled this.
        # TODO UNCOMMENT
        #elif "@cpsd.us" not in user_email:
        #    message = "Your email is not valid on this website."
        #    return render_template("status.html", message=message, block_title=block_title[0]), 400

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
        db.execute("INSERT INTO users (username, email, password) VALUES (:username, :email, :hashed_password)",
         {"username": user_inp, "email": user_email, "hashed_password": hashed_password})
        
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
        return redirect(url_for("index"))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")
    


@app.route("/logout")
def logout():
    # Logs user out
    session.clear()
    message = "Logged out!"
    return render_template("status.html", message=message, block_title=block_title[2])

# https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
def allowed_file(filename):
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Get the formatted date and time -- taken from project2
def get_formatted_dt():
    months = {
        "01": "January", "02": "February", "03": "March",
        "04": "April", "05": "May", "06": "June", "07": "July",
        "08": "August", "09": "September", "10": "October",
        "11": "November", "12": "December"}
    time = str(datetime.datetime.now().strftime("%I:%M %p"))
    date = str(datetime.datetime.now().date())
    month = date[5:7]
    month = months[month]
    day = date[8:10]

    # Get the correct ending for the day for the timestamp
    if date[9] == "1":
        dayStr = "st"
    elif date[9] == "2":
        dayStr = "nd"
    elif date[9] == "3":
        dayStr = "rd"
    else:
        dayStr = "th"

    day = day + dayStr

    timestamp = f"Posted at {time} on {month} {day}"

    return timestamp

@app.route("/create_post", methods=["POST", "GET"])
@login_required
def create_post():
    user_id = session["user_id"]
    check_super_user = db.execute("SELECT * FROM users WHERE user_id = :user_id", {"user_id":user_id}).fetchone()
    if check_super_user[4]:
        if request.method == "POST":
            if not check_super_user[1]:
                message = "Error: Could not find your username."
                return render_template("status.html", message=message)
            elif not request.form.get("title"):
                message = "Error: Could not find title/you forgot to enter a title."
                return render_template("status.html", message=message)
            elif not request.form.get("post-body"):
                message = "Error: Could not get the post contents."
                return render_template("status.html", message=message)

            title = request.form.get("title")

            date_posted = get_formatted_dt()

            content = request.form.get("post-body")

            author = check_super_user[1]
            
            returned_post = db.execute("SELECT * FROM posts WHERE title = :title", {"title": title}).fetchone()

            if returned_post != None:
                # TODO
                # Do some JavaScript possibly so title can be changed
                message = "Post with that title already exists"
                return render_template("status.html", message=message)
            
            # Got most (basically all) of the code from this website with documentation on how to do a lot of this stuff:
            # https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
            if request.files["file"].filename != "":
                # Never mind that just continue on and inject into database thru this path otherwise I will inject without img
                user_img = request.files["file"]
                filename = ""
                if user_img.filename == "":
                    return render_template("status.html", message="Error: There was no file name found")
                elif user_img and allowed_file(user_img.filename):
                    filename = secure_filename(user_img.filename)
                    filepath = "/static/images/" + str(filename)
                    returned_posts = db.execute("SELECT * FROM posts WHERE image_path = :image_path", {"image_path": filepath}).fetchone()
                    if returned_posts:
                        message = "Image name already exists. Failed to create post."
                        return render_template("status.html", message=message)
                    user_img.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                    db.execute("INSERT INTO posts (title, author, date_posted, content, image_path) VALUES (:title, :author, :date_posted, :content, :image_path)", {"title": title, "author": author, "date_posted": date_posted, "content": content, "image_path": filepath})
                    db.commit()
                    post_info = db.execute("SELECT * FROM posts WHERE title = :title", {"title": title}).fetchone()
                    post_id = post_info[0]
                    post_url = "post/" + str(post_id)
                    # TODO FIX URL REDIRECT AND INSTEAD SEND TO POST
                    return redirect(post_url)
                else:
                    if user_img.filename != "":
                        filename = user_img.filename
                        message = f"Error: This file ({filename}) is not accepted. Please provide an image."
                        return render_template("status.html", message=message)
                    else:
                        message = f"Error: This file is not accepted or found. Please provide an image."
                        return render_template("status.html", message=message)
                    
            else:
                db.execute("INSERT INTO posts (title, author, date_posted, content) VALUES (:title, :author, :date_posted, :content)", {"title": title, "author": author, "date_posted": date_posted, "content": content})
                db.commit()
                post_info = db.execute("SELECT * FROM posts WHERE title = :title", {"title": title}).fetchone()
                post_id = post_info[0]
                post_url = "post/" + str(post_id)
                return redirect(post_url)

                
            #add_post = db.execute("INSERT INTO posts () VALUES ()", {})
            #db.commit()
        else:
            return render_template("create_post.html")
    else:
        message = "You do not have permission to be here."
        return render_template("status.html", message=message, block_title=block_title[0]), 400


@app.route("/post_list")
def list_posts():
    post_list = db.execute("SELECT * FROM posts").fetchall()
    return render_template("post_list.html", posts=post_list)


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if request.method == "POST":
        try:
            update_user = int(request.form.get("user_info"))
            for a in range(15):
                print("HIT TRY")
        except:
            update_user = "%" + request.form.get("user_info") + "%"
            for a in range(15):
                print("HIT EXCEPT")
        # TODO
        # Just change this so it is not returning like but instead equal to
        if isinstance(update_user, int):
            returned_users = db.execute("SELECT * FROM users WHERE user_id = :user_info", {"user_info": update_user}).fetchall()
        else:
            returned_users = db.execute("SELECT * FROM users WHERE username LIKE :user_info OR email LIKE :user_info", {"user_info": update_user}).fetchall()

        for num in range(10):
            print(returned_users)
        if not update_user:
            message = "You forgot to fill in the field"
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        elif not returned_users:
            message = "Could not find that person in our database"
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        return render_template("user_list.html", users=returned_users)
    else:
        user_id = session["user_id"]
        check_super_user = db.execute("SELECT * FROM users WHERE user_id = :user_id", {"user_id":user_id}).fetchone()
        if check_super_user[4]:
            return render_template("admin_page.html", block_title=block_title[0])
        else:
            message = "You do not have permission to be here."
            return render_template("status.html", message=message, block_title=block_title[0]), 400
    


@app.route("/post/<post_id>", methods=["GET"])
def post(post_id):
    post = db.execute("SELECT * FROM posts WHERE post_id = :post_id", {"post_id": post_id}).fetchone()
    return render_template("post.html", post_info=post)


@app.route("/search", methods=["GET", "POST"])
@login_required
def search():

    # Test
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


@app.route("/make_admin/<update_user_id>")
@login_required
def make_admin(update_user_id):
    user_id = session["user_id"]
    check_super_user = db.execute("SELECT * FROM users WHERE user_id = :user_id", {"user_id": user_id}).fetchone()
    if check_super_user[4]:
        try:
            int(update_user_id)
        except:
            message = "That is not a valid ID."
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        db.execute("UPDATE users SET superuser = :superuser_status WHERE user_id = :user_id", {"superuser_status": True, "user_id": update_user_id})
        db.commit()
        # TODO
        # ADD BLOCK TITLE
        return render_template("admin_page.html")
    else:
        message = "You do not have permission to be here."
        return render_template("status.html", message=message, block_title=block_title[0]), 400

@app.route("/check_username", methods=["GET", "POST"])
def check_username():
    # Taken from my CS50's finance project
    for a in range(10):
        print("HIT CHECK_USERNAME")
    username = request.args.get("username")
    username_select = db.execute("SELECT * FROM users WHERE username = :username", {"username":username}).fetchone()
    if len(username) >= 1 and username_select == None:
        return jsonify(True)
    else:
        return jsonify(False)
