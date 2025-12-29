/*
=====================================================================================
| Important variables taken from the element with id "data".                        |
=====================================================================================
*/
const from_version = $("#data").data("from-version");
const to_version = $("#data").data("to-version");
const url_status = $("#data").data("url-status");
const url_classification = $("#data").data("url-classification");
const url_links = $("#data").data("url-links");

/*
=====================================================================================
| The following function implements the diff functionality to show the differences  |
| between the new and old description of a MITRE change on the click of a button.   |
=====================================================================================
*/
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

function setEventListenerClassification() {
    $(".classification").on("change", function() {
        const data = {
            from_version: from_version,
            to_version: to_version,
            mitre_id: $("#mitre-id").text(),
            target: $(this).attr("id"),
            value: $(this).val()
        }
        $.ajax({
            url: url_classification,
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify(data),
            dataType: "json",
            success: function(response) {
                $("#client-criticality-sum").text(response.client_criticality_sum);
                $("#infra-criticality-sum").text(response.infra_criticality_sum);
                $("#service-criticality-sum").text(response.service_criticality_sum);
            }
        })
    });
}

// Set prev link on a tag:
function setPrevAndNextLink() {
    // Get current filter of current upgrade.
    let filter = localStorage.getItem(`filter-${from_version}-${to_version}`);
    
    // Get category (tactic) from data fields.
    let category = $("#data").data("category");

    // Construct dict for API call.
    let data = {
        from_version: from_version,
        to_version: to_version,
        category: category,
        mitre_id: $("#mitre-id").text(),
        filter: filter
    }

    // Get prev and next link from backend and insert them into the <a> elements.
    $.ajax({
        url: url_links,
        method: "POST",
        contentType: "application/json",
        data: JSON.stringify(data),
        dataType: "json",
        success: function(response) {
            // Set previous and next link if they exist. If they don't exist add the links to the 'disabled' class.
            console.log(response);
            if (response.prev_url) {
                $("#prev").attr("href", response.prev_url);
            } else {
                $("#prev").addClass("disabled");
            }

            if (response.next_url) {
                $("#next").attr("href", response.next_url);
            } else {
                $("#next").addClass("disabled");
            }
        }
    });
}

setEventListenerDiffButton();
setEventListenerClassification();
setPrevAndNextLink();