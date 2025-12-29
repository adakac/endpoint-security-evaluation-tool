/*
==================================================================================
| Handle light and dark mode.                                                    |
==================================================================================
*/
$(document).ready(function() {
    // Load saved theme from LocalStorage.
    const saved_theme = localStorage.getItem("bs-theme");
    if (saved_theme) {
        $("html").attr("data-bs-theme", saved_theme);
    }

    // Change dark/light mode on button click and store to LocalStorage to remember the user's decision.
    $("#theme").on("click", function() {
        const current_theme = $("html").attr("data-bs-theme");
        const new_theme = current_theme === "light" ? "dark" : "light";
        $("html").attr("data-bs-theme", new_theme);
        localStorage.setItem("bs-theme", new_theme)
    });
});