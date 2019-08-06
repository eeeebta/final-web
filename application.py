import os
import datetime
import re
import string
import random

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for, jsonify
from flask_session import Session
from flask_mail import Mail, Message

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

@app.route("/")
def index():

    # Try and find at least one user from the users table
    users = db.execute("SELECT * FROM users").fetchone()

    # If there are no users set up an admin account once the owner or someone else visits the website
    # This way the owner has to basically never look at the database
    if not users:
        # Generate a secure password for admin
        password = gen_pass()

        # Hash it
        hashed = generate_password_hash(password)

        # Get the email
        email = str(os.getenv("EMAIL_USERNAME"))

        # Insert into the admin info into the database
        db.execute("INSERT INTO users (username, password, email, superuser) VALUES (:username, :password, :email, :superuser)", {"username": "admin", "password": hashed, "email": email, "superuser": True})

        # Save it
        db.commit()

        # Send an email out with the password
        msg = Message(
            body=f"Hello! \n\nThe password for logging in as admin is: {password} \n\n(Yes it is a long password but appreciate it)",
            subject="Admin password",
            recipients=email.split()
        )
        mail.send(msg)

    return render_template("index.html")


# In case a key is not present then have this url just send them to status
@app.route("/unsubscribe")
def unsub_nokey():
    message = "No key found"
    return render_template("status.html", message=message, block_title=block_title[0]), 400



# Unsubscribe a user using the key
@app.route("/unsubscribe/<key>")
def unsubscribe(key):
    if key in unsub_keys:
        user_id = unsub_keys[key]
    else:
        message = "Invalid key"
        return render_template("status.html", message=message, block_title=block_title[0]), 400
    e = db.execute("UPDATE users SET subscribed = :status WHERE user_id = :user_id", {"status": False, "user_id": user_id})
    db.commit()
    message = "Unsubscribed!"
    return render_template("status.html", message=message)


# Probably will not happen but in case a key is generated and it was
# already given to someone else I can store it here temporarily
# since most likely the person unsubscribing will delete the emails
# I am not sure that a database would be useful here
unsub_keys = {}
# Got the thing to generate the "key" from: https://stackoverflow.com/questions/2257441/random-string-generation-with-upper-case-letters-and-digits/23728630#23728630
def gen_rand_key(user_id):
    global unsub_keys
    user_id = user_id
    key = ""
    for _ in range(16):
        key += "".join(random.SystemRandom().choice(string.ascii_uppercase + string.digits))
    
    # If by some strange miracle the key is already in unsub keys then
    # generate a new one until there is no longer one that is in unsub keys
    while key in unsub_keys:
        key = ""
        for _ in range(16):
            key += "".join(random.SystemRandom().choice(string.ascii_uppercase + string.digits))

    # Add the key to unsub keys and the respective user_id
    unsub_keys[key] = user_id
    return key

# Generate a password for admin
def gen_pass():
    password = ""
    for _ in range(32):
        password += "".join(random.SystemRandom().choice(string.ascii_uppercase + string.digits))
    return password


# https://stackoverflow.com/questions/49226806/python-check-for-a-valid-email
# https://stackoverflow.com/questions/19030952/pep8-warning-on-regex-string-in-python-eclipse
def validate_email(email):
    return bool(re.match(
        "^.+@(\\[?)[a-zA-Z0-9-.]+.([a-zA-Z]{2,3}|[0-9]{1,3})(]?)$", email))

@app.route("/register", methods=["GET", "POST"])
def register():

    # Get all the fields
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

        result = db.execute("SELECT * FROM users WHERE username = :username", {"username": user_inp}).fetchone()

        # If it db.execute to find if username exists returns something then the username exists
        if result:
            message = "Username already exists"
            return render_template("status.html", message=message, block_title=block_title[0]), 400

        # Hashed the password and stored it in a variable
        hashed_password = generate_password_hash(p1)
        
        # If everything passed then insert user creds into the table 
        db.execute("INSERT INTO users (username, email, password) VALUES (:username, :email, :hashed_password)",
         {"username": user_inp, "email": user_email, "hashed_password": hashed_password})
        
        # Commit and add data into table
        db.commit()

        user = db.execute("SELECT * FROM users WHERE username = :username", {"username": user_inp}).fetchone()

        # Logs in the user automatically
        session["user_id"] = user[1]

        # Store the superuser status in session for jinja
        session["superuser"] = user[4]

        # Redirect user to home page
        return redirect(url_for("search_posts"))

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
    # In case somehow a user does not have a super user session status
    try:
        user_id = session["user_id"]
        check_super = session["superuser"]
    except KeyError:
        message = "There was an error. You may not have access to view this page."
        return render_template("status.html", message=message, block_title=block_title[0]), 400
    user = db.execute("SELECT * FROM users WHERE user_id = :user_id", {"user_id":user_id}).fetchone()
    user = user[1]

    # If the user is a super user then proceed
    if check_super:
        if request.method == "POST":

            # If I could not get the username then redirect to status with an error message
            if not user:
                message = "Error: Could not find your username."
                return render_template("status.html", message=message, block_title=block_title[0]), 400

            # If nothing was entered then throw an error
            elif not request.form.get("title"):
                message = "Error: Could not find title/you forgot to enter a title."
                return render_template("status.html", message=message, block_title=block_title[0]), 400

            # If the title is too long throw an error
            elif len(str(request.form.get("title"))) > 255:
                message = "Title too long. Shorten the title"
                return render_template("status.html", message=message, block_title=block_title[0]), 400

            # If the post body does not exist then throw an error
            elif not request.form.get("post-body"):
                message = "Error: Could not get the post contents."
                return render_template("status.html", message=message, block_title=block_title[0]), 400

            # Assign title the value of the title
            title = request.form.get("title")

            # Get the formatted time and date
            date_posted = get_formatted_dt()

            # Get the content
            content = request.form.get("post-body")

            # Get the author
            author = user

            # See if a post with the same title already exists
            returned_post = db.execute("SELECT * FROM posts WHERE title = :title", {"title": title}).fetchone()

            # If it does then throw an error
            if returned_post != None:
                message = "Post with that title already exists"
                return render_template("status.html", message=message, block_title=block_title[0]), 400
            
            # Got most (basically all) of the essential code from this website with documentation on how to do a lot of this stuff:
            # https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
            if request.files["file"].filename != "":
                user_file = request.files["file"]
                filename = ""

                # Check if a file was actually submitted
                if user_file.filename == "":
                    return render_template("status.html", message="Error: There was no file name found")

                # Check if it is a valid file
                elif user_file and allowed_file(user_file.filename):
                    filename = secure_filename(user_file.filename)
                    if filename[-3:] in video_formats:
                        filepath = "/static/videos/" + str(filename)
                    else:
                        filepath = "/static/images/" + str(filename)
                    
                    # If the filepath is too long then throw an error
                    if len(filepath) > 255:
                        message = "Filename too long. Please make the file name shorter."
                        return render_template("status.html", message=message, block_title=block_title[0]), 400
                    
                    # See if the image with the same name already exists
                    returned_posts = db.execute("SELECT * FROM posts WHERE image_path = :image_path", {"image_path": filepath}).fetchone()

                    # Throw an error
                    if returned_posts:
                        message = "Image or video name already exists. Failed to create post."
                        return render_template("status.html", message=message, block_title=block_title[0]), 400

                    # If a video was uploaded then save it to the correct folder
                    if "videos" in filepath:
                        user_file.save(os.path.join(VIDEO_FOLDER, filename))

                    # Otherwise save it to images
                    else:
                        user_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

                    # Create the post
                    db.execute("INSERT INTO posts (title, author, date_posted, content, image_path) VALUES (:title, :author, :date_posted, :content, :image_path)", {"title": title, "author": author, "date_posted": date_posted, "content": content, "image_path": filepath})

                    # Save
                    db.commit()

                    # Get the post info
                    post_info = db.execute("SELECT * FROM posts WHERE title = :title", {"title": title}).fetchone()

                    # Get the post id to redirect or link
                    post_id = post_info[0]

                    # Assemble the redirect link for the poster
                    post_url_client = "post/" + str(post_id)

                    # Send an email to everyone who is not an admin and is subscribed
                    notify = db.execute("SELECT * FROM users WHERE superuser = :superuser AND subscribed = :subscribed", {"superuser": False, "subscribed": True}).fetchall()

                    # Get all of the url info so I can use this with any url without having to change code
                    url_root = request.url_root
                    post_url = f"{url_root}post/{post_id}"
                    title = f"New Post: {title}"
                    
                    # If the email was not sent then return an error which should not happen
                    if not send_mail(notify, url_root, title, post_url):
                        message = "Something went wrong while sending emails..."
                        return render_template("status.html", message=message, block_title=block_title[0]), 400
                    
                    # Redirect poster to the new post
                    return redirect(post_url_client)

                # If a file was attached but was not valid then throw an error
                else:
                    if user_file.filename != "":
                        filename = user_file.filename
                        message = f"Error: This file ({filename}) is not accepted. Please provide an image."
                        return render_template("status.html", message=message, block_title=block_title[0]), 400
                    else:
                        message = f"Error: This file is not accepted or found. Please provide an image."
                        return render_template("status.html", message=message, block_title=block_title[0]), 400
            
            # Otherwise if no image or video was attached then go through this
            else:

                # Inser the post into the database
                db.execute("INSERT INTO posts (title, author, date_posted, content) VALUES (:title, :author, :date_posted, :content)", {"title": title, "author": author, "date_posted": date_posted, "content": content})
                db.commit()

                # Get the post info
                post_info = db.execute("SELECT * FROM posts WHERE title = :title", {"title": title}).fetchone()

                # Redirect
                post_id = post_info[0]
                post_url_client = "post/" + str(post_id)

                # Send an email to everyone who is not an admin
                notify = db.execute("SELECT * FROM users WHERE superuser = :superuser AND subscribed = :subscribed", {"superuser": False, "subscribed": True}).fetchall()

                # The url stuff
                url_root = request.url_root
                post_url = f"{url_root}post/{post_id}"
                title = f"New Post: {title}"

                # Check if emails are sent
                if not send_mail(notify, url_root, title, post_url):
                    message = "Something went wrong while sending emails..."
                    return render_template("status.html", message=message, block_title=block_title[0]), 400
                
                return redirect(post_url_client)
        
        # Otherwise if the method is get then just render the template
        else:
            return render_template("create_post.html")
    
    # If the user is not an admin then do not give them permission to view the page
    else:
        message = "You do not have permission to be here."
        return render_template("status.html", message=message, block_title=block_title[0]), 400


# Function used to send mail
def send_mail(people, url_root, title, post_url):
    # Taken from the flask-mail documentation
    with mail.connect() as conn:
        for person in people:
            key = gen_rand_key(person[0])
            email = person[3]
            unsub_url = f"{url_root}unsubscribe/{key}"
            subject = title
            message = f"Hello, {person[1]}! \n\nCheck out this new post! You can view it at: {post_url} \n\n- Some closing for this email \n\n Unsubscribe here if you no longer want these emails: {unsub_url}"
            msg = Message(recipients=email.split(),
            body=message,
            subject=subject)
            conn.send(msg)
        return True
    return False


# Get all the posts and list them
@app.route("/post_list", methods=["GET"])
def list_posts():
    post_list = db.execute("SELECT * FROM posts").fetchall()
    return render_template("post_list.html", posts=post_list)


# Admin page
@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():

    # If a post method then do this
    if request.method == "POST":

        # If somehow someone was able to get to post but is not a superuser then reject them and send them to status
        if not session["superuser"]:
            message = "You do not have permission to view this page"
            return render_template("status.html", message=message, block_title=block_title[0]), 400

        
        # If I cannot make the "user_info" into an int then I should except with a ValueError and instead use it as a string
        try:
            update_user = int(request.form.get("user_info"))
        except ValueError:
            update_user = "%" + request.form.get("user_info") + "%"

        # If the length of it is longer than 255 then just redirect to the status page with the error message
        if len(update_user) > 255:
            message = "That query is too long so this user probably does not exist on the database."
            return render_template("status.html", message=message, block_title=block_title[0]), 400

        # If the field did not have anything typed into it then return an error
        elif not update_user:
            message = "You forgot to fill in the field"
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        
        # Search by user ID and by everything else
        if isinstance(update_user, int):
            returned_users = db.execute("SELECT * FROM users WHERE user_id = :user_info AND superuser = :status", {"user_info": update_user, "status": False}).fetchall()
        else:
            returned_users = db.execute("SELECT * FROM users WHERE (username LIKE :user_info AND superuser = :status) OR (email LIKE :user_info AND superuser = :status)", {"user_info": update_user, "status": False}).fetchall()

        # If no users were returned then throw an error and redirect to status page
        if not returned_users:
            message = "Could not find that person in our database or the person is already a super user"
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        return render_template("user_list.html", users=returned_users)
    
    # If the method was get then just render the page IF the user is a superuser
    else:
        # Get superuser status from session
        check_super = session["superuser"]

        # Return admin page if admin
        if check_super:
            return render_template("admin_page.html", block_title=block_title[0]), 400

        # Else redirect to status page and have an error message
        else:
            message = "You do not have permission to be here."
            return render_template("status.html", message=message, block_title=block_title[0]), 400
    

# Get the post from the database
@app.route("/post/<post_id>", methods=["GET"])
@login_required
def post(post_id):

    # Find the post
    post = db.execute("SELECT * FROM posts WHERE post_id = :post_id", {"post_id": post_id}).fetchone()

    # If it is not found then return the status page and give an error message
    if not post:
        message = "Could not find that post."
        return render_template("status.html", message=message, block_title=block_title[0]), 400
    
    # If there is a post then return the post template with the post info
    return render_template("post.html", post_info=post)


# Search for posts
@app.route("/search_posts", methods=["GET", "POST"])
@login_required
def search_posts():

    # If method is post then return the list of posts
    if request.method == "POST":

        # If there is no search query then 
        if not request.form.get("search"):
            message = "You did not enter anything in the search box"
            return render_template("status.html", message=message, block_title=block_title[0]), 400

        # Get the query and pass it into SQL
        q = "%" + request.form.get("search") + "%"
        qr = db.execute("SELECT * FROM posts WHERE title LIKE :q OR content LIKE :q OR author LIKE :q OR date_posted LIKE :q", {"q": q}).fetchall()
        

        # If I could not find the post then I render the error page
        if not qr:
            message = "Your query did not match anything in our databases."
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        
        # If I can then just return the list of posts
        return render_template("returned_posts.html", returned_posts=qr)
    
    # If get method then just render the search page
    else:
        return render_template("search_posts.html")


# Make a user an admin if the user making the person an admin is an admin
@app.route("/make_admin/<update_user_id>", methods=["GET", "POST"])
@login_required
def make_admin(update_user_id):
    if request.method == "GET":
        message = "That is not a valid method to access this webpage"
        return render_template("status.html", message=message, block_title=block_title[0]), 400
    user_id = update_user_id
    check_super = session["superuser"]
    user = db.execute("SELECT * FROM users WHERE user_id = :user_id", {"user_id": user_id}).fetchone()
    user = user[1]

    # If they are a super user then allow them to make the other person into an admin
    if check_super:
        if isinstance(update_user_id, int):
            int(update_user_id)
        else:
            message = "That is not a valid ID."
            return render_template("status.html", message=message, block_title=block_title[0]), 400
        db.execute("UPDATE users SET superuser = :superuser_status WHERE user_id = :user_id", {"superuser_status": True, "user_id": update_user_id})
        db.commit()
        message = f"{user} has been made into an admin"
        return render_template("admin_page.html", message=message, block_title="Admin")
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
    # Same code used in check username

    # Get the title
    title = request.args.get("title")

    # Check if the post exists
    posts = db.execute("SELECT * FROM posts WHERE title = :title", {"title": title}).fetchone()

    # String the title since at some point I got an error
    title = str(title)

    # Check if the length of the title is greater than or equal to one and that a post does not exist
    if len(title) >= 1 and posts == None:
        return jsonify(True)
    
    # If a post exists then return false
    else:
        return jsonify(False)
