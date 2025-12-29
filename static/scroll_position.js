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

        // Select the element and get the top offset, then subtract 200 due to the fixed navbar.
        let element = $(`#${highlightID}`);
        let offset = element.offset().top - 200;

        // Scroll to the position from above.
        window.scrollTo({top: offset, behavior: "smooth"});

        // Highlight the entire row where the element is for 5 seconds.
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