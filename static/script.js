// ==================================================================================
// | Handle light and dark mode.                                                    |
// ==================================================================================
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
    })
})

// Dynamically update and calculate the current progress.
function updatePercentage(category) {
    // Dynamically get all select elements in total and count how many have selected "Done".
    // Then calculate the new percentage and update the upper heading.
    let total_done_count = 0;
    let total_count = 0;
    $(".status-select").each(function() {
        if ($(this).val() == "Done") {
            total_done_count++;
        }
        total_count++;
    });
    let percentage_total = (total_done_count / total_count * 100).toFixed(2);
    $("#status-total").text(`Total: ${percentage_total}%`)

    // Dynamically get all select elements per category and count the total and how many have selected "Done".
    // Then calculate the new percentage and update the category heading.
    let category_done_count = 0;
    let category_count = 0;        
    $(`.status-select[data-category="${category}"]`).each(function() {
        if ($(this).val() === "Done") {
            category_done_count++;
        }
        category_count++;
    });
    let percentage_category = (category_done_count / category_count * 100).toFixed(2);
    $(`#status-${category}`).text(`Status: ${percentage_category}%`);
}

// The following function sets an event listener on a <select> tag that let's users change the status of a change.
// The request is being sent via Ajax, so the site can be dynamically updated.
// If the request was successfull, the progress is updated (in percentage).
function setEventListenerStatusSelect(url, from_version, to_version) {
    $(".status-select").on("change", function() {
        const mitre_id = $(this).data("mitre");
        const status = $(this).val();
        const category = $(this).data("category");

        const data = {
            from_version: from_version,
            to_version: to_version,
            mitre_id: mitre_id,
            status: status
        };

        // https://api.jquery.com/jQuery.ajax/
        $.ajax({
            url: url,
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify(data),
            success: function(response) {
                // Dots are invalid in IDs.
                mitre = mitre_id.replace(".", "-");
                const icon = $(`#icon-${mitre}`);
                icon.removeClass("bi-check bi-hourglass-split bi-ban text-success text-warning text-danger");
                
                // Change the icon.
                if (status === "Done") {  
                    icon.addClass("bi-check text-success");
                }
                else if (status == "In Progress") {
                    icon.addClass("bi-hourglass-split text-warning");
                }
                else if (status == "Not Done") {
                    icon.addClass("bi-ban text-danger");
                }

                if (category) {
                    updatePercentage(category);
                }
            }
        });
    });
}


function setEventListenerDiffButton() {
    // Flag to check if text has changed.
    let changed = false;

    // Original body for restoring site.
    const original_old_description = $("#old-description").html();
    const original_new_description = $("#new-description").html();

    // Set EventListener on the button. On click it should show the diff.
    $("#diff-button").on("click", function() {
        // Get all p and li tags from old and new description.
        const old_description = $("#old-description p, #old-description li");
        const new_description = $("#new-description p, #new-description li");

        if (original_old_description == original_new_description) {
            console.log("No Diffs found.");
            return;
        }

        if (!changed) {
            // Iterate over li and p tags and change the html to show the differences.
            new_description.each(function(index) {
                const new_text = $(this).text();
                const old_text = old_description.eq(index).text() || "";
                const diff = Diff.diffWords(old_text, new_text);
                let result = "";

                // For each set of different words:
                diff.forEach(function(text) {
                    if (text.added) {
                        result += `<span class="added">${text.value}</span>`;
                    } else if (text.removed) {
                        result += `<span class="removed">${text.value}</span>`
                    } else {
                        result += text.value;
                    }
                });
                $(this).html(result);
            });
            changed = true;
        } else {
            // Restore site if button is clicked again.
            $("#old-description").html(original_old_description);
            $("#new-description").html(original_new_description);
            changed = false;
        }
    });
}