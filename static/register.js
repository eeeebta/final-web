document.addEventListener("DOMContentLoaded", () => {
    document.querySelector("form").onsubmit = (event) => {
        // Prevent submission
        event.preventDefault();
        // This checks if username is available
        // It also makes sure that the email, password, and password confirmation are valid

        // Get email
        let email = document.querySelector("#email").value

        // Get password
        let password = document.querySelector("#password").value

        // Get confirmation
        let confirmation = document.querySelector("#confirmation").value


        // Go through everything before getting to the ajax

        // Check if the email exists
        if (!email) {
            alert("You forgot to fill in the email field");
        }
        
        // Check if the password exists
        else if (!password) {
            alert("You forgot to fill in the password field");
        }

        // Check if the password was confirmed
        else if (!confirmation) {
            alert("You did not confirm your password");
        }

        // Finally check username and submit if it is valid
        else {
            $.get("check_username", {username: document.querySelector("#username").value}, (data) => { 
                // If so then you can submit
                if (data) {
                    document.querySelector("form").submit();
                // Alert person that username is already taken
                } 
                else {
                    alert("Username is taken");
                }
            });
        }
        
    };
});