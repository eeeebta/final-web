document.addEventListener("DOMContentLoaded", () => {

    // https://www.w3schools.com/bootstrap4/bootstrap_forms_custom.asp
    $(".custom-file-input").on("change", function() {
        var fileName = $(this).val().split("\\").pop();
        $(this).siblings(".custom-file-label").addClass("selected").html(fileName);
    });

    document.querySelector("form").onsubmit = (event) => {
        // Prevent submission
        event.preventDefault();
        // This checks if the post title is available
        // It also makes sure that the post body and title are valid

        // Get title
        let title = document.querySelector("#title").value

        // Get the post body
        let content = document.querySelector("#post-body").value

        // Go through everything before getting to the ajax

        // Check if the title exists
        if (!title) {
            alert("You forgot the title.");
        }
        
        // Check if the password exists
        else if (!content) {
            alert("How did you forget the content of the post?");
        }

        // Finally check the post title and submit if it is valid
        else {
            $.get("check_post", {title: document.querySelector("#title").value}, (data) => { 

                // If so then you can submit
                if (data) {
                    document.querySelector("form").submit();
                
                // Alert person that the post title has already been taken
                } 
                else {
                    alert("Post title has already been used before");
                }
            });
        }
        
    };
});