/*
This script saves and restores the scroll position when the user gets back to the overview page.
*/

// Get the page from where the JS file is called (e.g. change.html).
const page = $("#data").data("page");

if (page === "changes.html") {
    // Save the ID of the element that was clicked on.
    $(".mitre-link").on("click", function() {
        localStorage.setItem("highlightID", $(this).attr("id"));
    });

    // Scroll down to the element when the site loads again.
    $(window).on("load", function() {
        let highlightID = localStorage.getItem("highlightID");

        if (!highlightID) {
            return;
        }

        // Scroll down to the element.
        let element = $(`#${highlightID}`);
        element[0].scrollIntoView();

        // Highlight the entire row where the element is.for 5 seconds.
        let row = element.closest("tr");
        row.addClass("highlight");
        setTimeout(function() {
            row.removeClass("highlight");
        }, 5000);

        // Remove again, so it doesn't highlight when the page is simply reloaded.
        localStorage.removeItem("highlightID");
    });
}

if (page === "change.html") {
    // Dynamically adjust the position when clicking on the 'previous' and 'next' links in the Overview pages.
    $(window).on("load", function() {
        let id = $("#data").data("id");
        localStorage.setItem("highlightID", id);
    });
}