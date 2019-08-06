document.addEventListener("DOMContentLoaded", () => {
    // https://stackoverflow.com/questions/48049300/page-redirect-after-x-seconds-wait-using-flask-python-jinja
    // https://www.w3schools.com/jsref/met_win_settimeout.asp
    window.setTimeout( () => {
        // Redirect to index
        window.location.href = "/";
    }, 5000);
});
