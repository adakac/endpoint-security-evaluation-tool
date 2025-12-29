/*
This script saves and restores the scroll position when the user gets back to the overview page.
*/

// Save scroll position, when clicking on a link.
$(".mitre-link").on("click", function() {
    localStorage.setItem("scrollPosition", $(window).scrollTop());
    localStorage.setItem("highlightID", $(this).attr("id"));
});

// Restore scroll position when going back.
$(window).on("load", function() {
    // Reset scroll position.
    const pos = localStorage.getItem("scrollPosition");
    console.log(pos);
    if (pos !== null) {
        $(window).scrollTop(pos);
        localStorage.setItem("scrollPosition", 0);
    }

    // Highlight the element when returning to the page.
    const highlightID = localStorage.getItem("highlightID");
    if (highlightID) {
        const element = $("#" + highlightID).closest("tr");
        element.addClass("highlight");
        setTimeout(() => {
            element.removeClass("highlight");
        }, 5000);
    }
    localStorage.removeItem("highlightID");
});