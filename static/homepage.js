/*
=====================================================================================
| Determine the version and display a help text for the user.                       |
=====================================================================================
*/
$("#version_select").on("change", function() {
    // Get all option elements from the dropdown menu and execute the val() function on each one,
    // to get their value. Then execute get() to get a JavaScript array.
    const versions = $("#version_select option").map(function() {
        return $(this).val();
    }).get()

    const selected_version = $("#version_select").val();
    
    // Minus 1, because of descending order.
    const index = versions.indexOf(selected_version) - 1;
    const next_version = versions[index];

    if (next_version === undefined) {
        $("#text").text("You are already on the newest version.");
    } else {
        $("#text").text(`You selected ${selected_version} and you want to upgrade to ${next_version}. Is this correct?`);
    }
});



/*
=====================================================================================
| Call the backend function to initiate an upgrade.                                 |
=====================================================================================
*/
$("#upgrade_form").on("submit", function(e) {
    e.preventDefault();
    $.ajax({
        url: $(this).attr("action"),
        method: "POST",
        data: $(this).serialize(),
        success: function(response) {
            $("#status-message").html(response.message);
            $("#status").removeClass("alert-warning").addClass("alert-primary");
            $("#status").show();
            $("#upgrades").prepend(`
                <li>
                    <a href=${response.url} target="_blank">
                        ${response.url_text}
                    </a>
                </li>`
            );
        },
        error: function(xhr) {
            console.log(xhr);
            message = xhr.responseJSON.message;
            $("#status-message").html(message);
            $("#status").removeClass("alert-primary").addClass("alert-warning");
            $("#status").show();
        }
    });
});