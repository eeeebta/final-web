document.addEventListener("DOMContentLoaded", () => {
    document.querySelector("form").onsubmit = (event) => {
        // Prevent submission
        event.preventDefault();
        // Checks if username is available
        $.get("check_username", {username: document.querySelector("#username").value}, (data) => { 
            // If so then you can submit
            if (data) {
                document.querySelector("form").submit();
            // Alert person that username is already taken
            } 
            else {
                alert("username is taken");
            }
        });
    };
});