document.addEventListener("DOMContentLoaded", () => {

    document.querySelector("form").onsubmit = (event) => {
        // Prevent submission
        event.preventDefault();
        // This checks and makes sure that everything is filled in

        // Get username
        let username = document.querySelector("#username").value

        // Get password
        let password = document.querySelector("#password").value

        // Check that username exists
        if (!username) {
            alert("You forgot your username");
        }
        
        // Check that password exists
        else if (!password) {
            alert("You forgot to type in a password");
        }

        // Finally submit if everything has passed
        else {
            document.querySelector("form").submit();
        }
        
    };
});