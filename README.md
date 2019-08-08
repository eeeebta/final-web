# final-project

## Project Description

(The description here will probably be much of what is on my index page)

Basically this project is akin to something like a blog that I will use throughout the rest of my high school years and use it as sort of a way to show progress of my personal projects and writing parts of papers in this as well. Application.py is almost the entire body of this webapp/page. It contains all the functions and routes. Within the html files are just basic templates that I use for the website. Also, layout.html is used on every other html page as a base. Within the JavaScript files are basically just all checking to make sure that everything will work before sending everything off to the server. In styles.css, I have some mobile responsiveness (through media queries) in order to make the website does not look bad on phones. I also have some other classes that I use throughout some pages. In helpers.py is the one function that I use to make check that a user is logged in before accessing a function. There is nothing currently in my images or videos folder, but once posts are made it can accept png, jpeg/jpg, gif and mp4. They will be filtered out to each respective folder.

## Database

My database has two tables. One was a users table with the columns of user_id (primary, int), username (char var, 255), password (char var, 255), email (char var, 255), subscribed (bool), and superuser (bool). The other table was called posts with the columns of post_id (primary, int), title (char var, 255), contents (text), author (char var, 255), date_posted (char var, 255), and image_path (char var, 255).

## Other import information

In order to run this you HAVE to run these commands:

export FLASK_APP=application.py

(I kept flask debug on because it would not let me run it without it)
export FLASK_DEBUG=1

export SECRET_KEY=[your secret key]
export EMAIL_USERNAME=[your email]
export EMAIL_PASSWORD=[email password]
export EMAIL_SERVER=[your email server. I used gmail when testing this so I did smtp.gmail.com]
export DATABASE_URL=[database url from heroku or somewhere else]
flask run
