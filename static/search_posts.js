document.addEventListener("DOMContentLoaded", () => {

    document.querySelector("form").onsubmit = (event) => {

        // Stop the form from submitting
        event.preventDefault();

        // Get the search value
        q = document.querySelector("#search").value;

        // If there is nothing in the search box alert
        if (!q) {
            alert("There is nothing in the search box");
        }

        // Otherwise submit
        else {
            document.querySelector("form").submit();
        }
    }
    
});
