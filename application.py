import os
import requests
import datetime
import re
import string
import random

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
VIDEO_FOLDER = join(dirname(realpath(__file__)), "static/videos/")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "mp4"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Check for environment variables
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")
elif not os.getenv("EMAIL_USERNAME"):
    raise RuntimeError("EMAIL_USERNAME is not set (example@example.com)")
elif not os.getenv("EMAIL_PASSWORD"):
    raise RuntimeError("EMAIL_PASSWORD is not set (for gmail enable 2FA and gen an app password)")
elif not os.getenv("EMAIL_SERVER"):
    raise RuntimeError("EMAIL_SERVER is not set (for gmail use 'smtp.gmail.com')")

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

# Secret key
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

# Configure flask mail app
# For obvious reasons I did not hardcode my own email details
# Since this needs to be configured from os env, this requires
# The export EMAIL_USERNAME=<username> command and same for 
# EMAIL_PASSWORD and EMAIL_SERVER
# https://stackoverflow.com/questions/37058567/configure-flask-mail-to-use-gmail
# https://pythonhosted.org/Flask-Mail/
app.config.update(
    MAIL_SERVER = str(os.getenv("EMAIL_SERVER")),
    MAIL_PORT = 465,
    MAIL_USE_SSL = True,
    MAIL_DEFAULT_SENDER = str(os.getenv("EMAIL_USERNAME")),
    MAIL_USERNAME = str(os.getenv("EMAIL_USERNAME")),
    MAIL_PASSWORD = str(os.getenv("EMAIL_PASSWORD"))
)

Session(app)

mail = Mail(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

block_title = ["Error", "Success", "Logged out"]

video_formats = ["mp4"]

# Possibly another database for this? TODO
common_passwords = []

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/unsubscribe/<key>")
def unsubscribe(key):
    if not key:
        message = "No key found"
        return render_template("status.html", message=message, block_title=block_title[0])
    else:
        try:
            user_id = unsub_keys[key]
        except:
            message = "Do not place keys in here randomly"
            return render_template("status.html", message=message, block_title=block_title[0])
        db.execute("UPDATE users SET subscribed = :status WHERE user_id = :user_id", {"user_id": user_id, "status": False})
        message = "Unsubscribed!"
        return render_template("status.html", message=message)

# Probably will not happen but in case a key is generated and it was
# already given to someone else I can store it here temporarily
# since most likely the person unsubscribing will delete the email
# I am not sure that a database would be useful here
unsub_keys = {}
global unsub_keys
# Got the thing to generate the "key" from: https://stackoverflow.com/questions/2257441/random-string-generation-with-upper-case-letters-and-digits/23728630#23728630
def gen_rand_key():
    user_id = session["user_id"]
    for _ in range(16):
        key = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits))
    unsub_keys[key] = user_id
    return key
    


# https://stackoverflow.com/questions/49226806/python-check-for-a-valid-email
# https://stackoverflow.com/questions/19030952/pep8-warning-on-regex-string-in-python-eclipse
def validate_email(email):
    return bool(re.match(
        "^.+@(\\[?)[a-zA-Z0-9-.]+.([a-zA-Z]{2,3}|[0-9]{1,3})(]?)$", email))

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
        elif not user_email:
            message = "Email not provided"
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        
        # If I was actually using this website I would probably just check for the ending that
        # everyone has in their email address as school instead of using this to validate the email
        elif not validate_email(user_email):
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

        # Store the superuser status in session for jinja
        session["superuser"] = result[4]

        # Redirect user to home page
        return redirect(url_for("search_post"))

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
        # Also ensures that the user exists inside the database
        if not rows or not check_password_hash(rows[2], request.form.get("password")):
            message = "Invalid username and/or password."
            return render_template("status.html", message=message, block_title=block_title[0]), 400

        # Remember which user has logged in
        session["user_id"] = rows[0]
        session["superuser"] = rows[4]

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


# TODO REMOVE
#@app.route("/logout_status", methods=["GET", "POST"])
#def logout_status():
#    if logout_status_info:
#        return jsonify(True)
#    else:
#        return jsonify(False)

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

# TODO ADD LOGIN REQUIRED
@app.route("/create_post", methods=["POST", "GET"])
@login_required
def create_post():
    user_id = session["user_id"]
    check_super = session["superuser"]
    user = db.execute("SELECT * FROM users WHERE user_id = :user_id", {"user_id":user_id}).fetchone()
    user = user[1]
    if check_super:
        if request.method == "POST":
            if not user:
                message = "Error: Could not find your username."
                return render_template("status.html", message=message, block_title=block_title[0])
            elif not request.form.get("title"):
                message = "Error: Could not find title/you forgot to enter a title."
                return render_template("status.html", message=message, block_title=block_title[0])
            elif not request.form.get("post-body"):
                message = "Error: Could not get the post contents."
                return render_template("status.html", message=message, block_title=block_title[0])

            title = request.form.get("title")

            date_posted = get_formatted_dt()

            content = request.form.get("post-body")

            author = user
            
            returned_post = db.execute("SELECT * FROM posts WHERE title = :title", {"title": title}).fetchone()

            if returned_post != None:
                # TODO
                # Do some JavaScript possibly so title can be changed
                message = "Post with that title already exists"
                return render_template("status.html", message=message, block_title=block_title[0])
            
            # Got most (basically all) of the code from this website with documentation on how to do a lot of this stuff:
            # https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
            if request.files["file"].filename != "":
                # Never mind that just continue on and inject into database thru this path otherwise I will inject without img
                user_file = request.files["file"]
                filename = ""
                if user_file.filename == "":
                    return render_template("status.html", message="Error: There was no file name found")
                elif user_file and allowed_file(user_file.filename):
                    filename = secure_filename(user_file.filename)
                    if filename[-3:] in video_formats:
                        filepath = "/static/videos/" + str(filename)
                    else:
                        filepath = "/static/images/" + str(filename)
                    
                    if len(filepath) > 255:
                        message = "Filename too long. Please make the file name shorter."
                        return render_template("status.html", message=message, block_title=block_title[0])
                    
                    returned_posts = db.execute("SELECT * FROM posts WHERE image_path = :image_path", {"image_path": filepath}).fetchone()
                    if returned_posts:
                        message = "Image or video name already exists. Failed to create post."
                        return render_template("status.html", message=message, block_title=block_title[0])
                    if "videos" in filepath:
                        user_file.save(os.path.join(VIDEO_FOLDER, filename))
                    else:
                        user_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                    db.execute("INSERT INTO posts (title, author, date_posted, content, image_path) VALUES (:title, :author, :date_posted, :content, :image_path)", {"title": title, "author": author, "date_posted": date_posted, "content": content, "image_path": filepath})
                    db.commit()
                    post_info = db.execute("SELECT * FROM posts WHERE title = :title", {"title": title}).fetchone()
                    post_id = post_info[0]
                    post_url_client = "post/" + str(post_id)

                    # TODO possibly move to function
                    # Send an email to everyone who is not an admin
                    notify = db.execute("SELECT * FROM users WHERE superuser = :superuser AND subscribed = :subscribed", {"superuser": False, "subscribed": True}).fetchall()
                    notify_people = []
                    for person in notify:
                        notify_people.append(person[3])
                    url_root = request.url_root
                    post_url = f"{url_root}post/{post_id}"
                    title = f"New Post: {title}"
                    unsub_url = f"{url_root}unsubscribe/"
                    mail.send_message(
                        title,
                        recipients=notify_people,
                        body=f"Hello! \n\nCheck out this new post! You can view it at: {post_url} \n\n- Some closing for this email \n\nUnsubscribe here if you no longer want these emails: {unsub_url}")
                    
                    # TODO FIX URL REDIRECT AND INSTEAD SEND TO POST
                    return redirect(post_url_client)
                else:
                    if user_file.filename != "":
                        filename = user_file.filename
                        message = f"Error: This file ({filename}) is not accepted. Please provide an image."
                        return render_template("status.html", message=message, block_title=block_title[0])
                    else:
                        message = f"Error: This file is not accepted or found. Please provide an image."
                        return render_template("status.html", message=message, block_title=block_title[0])
                    
            else:
                db.execute("INSERT INTO posts (title, author, date_posted, content) VALUES (:title, :author, :date_posted, :content)", {"title": title, "author": author, "date_posted": date_posted, "content": content})
                db.commit()
                post_info = db.execute("SELECT * FROM posts WHERE title = :title", {"title": title}).fetchone()
                post_id = post_info[0]
                post_url_client = "post/" + str(post_id)

                # Send an email to everyone who is not an admin
                notify = db.execute("SELECT * FROM users WHERE superuser = :superuser", {"superuser": False}).fetchall()
                notify_people = []
                for person in notify:
                    notify_people.append(person[3])
                url_root = request.url_root
                post_url = f"{url_root}post/{post_id}"
                title = f"New Post: {title}"
                mail.send_message(
                    title,
                    recipients=notify_people,
                    body=f"Hello! \n\nCheck out this new post! You can view it at: {post_url} \n\n - Some closing for this email")
                return redirect(post_url_client)

                
            #add_post = db.execute("INSERT INTO posts () VALUES ()", {})
            #db.commit()
        else:
            return render_template("create_post.html")
    else:
        message = "You do not have permission to be here."
        return render_template("status.html", message=message, block_title=block_title[0]), 400


@app.route("/post_list", methods=["GET"])
def list_posts():
    post_list = db.execute("SELECT * FROM posts").fetchall()
    return render_template("post_list.html", posts=post_list)


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if request.method == "POST":
        try:
            update_user = int(request.form.get("user_info"))
        except:
            update_user = "%" + request.form.get("user_info") + "%"
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
        check_super = session["superuser"]
        user = db.execute("SELECT * FROM users WHERE user_id = :user_id", {"user_id":user_id}).fetchone()
        user = user[1]
        if check_super:
            return render_template("admin_page.html", block_title=block_title[0])
        else:
            message = "You do not have permission to be here."
            return render_template("status.html", message=message, block_title=block_title[0]), 400
    


@app.route("/post/<post_id>", methods=["GET"])
def post(post_id):
    post = db.execute("SELECT * FROM posts WHERE post_id = :post_id", {"post_id": post_id}).fetchone()
    if not post:
        message = "Could not find that post."
        return render_template("status.html", message=message, block_title=block_title[0])
    return render_template("post.html", post_info=post)


# UPDATE THIS TODO
@app.route("/search_posts", methods=["GET", "POST"])
@login_required
def search_posts():

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
        return render_template("search_posts.html")


@app.route("/make_admin/<update_user_id>")
@login_required
def make_admin(update_user_id):
    user_id = session["user_id"]
    check_super = session["superuser"]
    user = db.execute("SELECT * FROM users WHERE user_id = :user_id", {"user_id": user_id}).fetchone()
    user = user[1]
    if check_super:
        try:
            int(update_user_id)
        except:
            message = "That is not a valid ID."
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        db.execute("UPDATE users SET superuser = :superuser_status WHERE user_id = :user_id", {"superuser_status": True, "user_id": update_user_id})
        db.commit()
        # TODO
        # ADD BLOCK TITLE
        return render_template("admin_page.html", block_title="Admin")
    else:
        message = "You do not have permission to be here."
        return render_template("status.html", message=message, block_title=block_title[0]), 400

# Used for ajax and to inform user as to if the username is available
@app.route("/check_username", methods=["GET", "POST"])
def check_username():
    # Taken from my CS50's finance project
    username = request.args.get("username")
    username_select = db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone()
    if len(username) >= 1 and username_select == None:
        return jsonify(True)
    else:
        return jsonify(False)

# Same thing as the function above, except this time it is used to make sure the post is valid
@app.route("/check_post", methods=["GET", "POST"])
def check_title():
    # The same code used for checking the validity of the post
    title = request.args.get("title")
    posts = db.execute("SELECT * FROM posts WHERE title = :title", {"title": title}).fetchone()
    title = str(title)
    if len(title) >= 1 and posts == None:
        return jsonify(True)
    else:
        return jsonify(False)
