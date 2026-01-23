/*
=====================================================================================
| Important variables taken from the element with id "data".                        |
=====================================================================================
*/
const from_version = $("#data").data("from-version");
const to_version = $("#data").data("to-version");
const mitre_id = $("#mitre-id").text();
const url_status = $("#data").data("url-status");
const url_classification = $("#data").data("url-classification");
const url_links = $("#data").data("url-links");
const url_evaluation_status = $("#data").data("url-evaluation-status");
const url_change_reasoning_and_measures = $("#data").data("url-reasoning-and-measures");

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

        // No difference found.
        if (original_old_description == original_new_description) {
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


/*
=====================================================================================
| When the classification of a technique is changed, this function updates it in    |
| the backend as well in the frontend.                                              |
=====================================================================================
*/
function setEventListenerClassification() {
    $(".classification").on("change", function() {
        const data = {
            from_version: from_version,
            to_version: to_version,
            mitre_id: mitre_id,
            target: $(this).attr("id"), // "client-criticality", "confidentiality", etc...
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

/*
=====================================================================================
| This function dynamically gets and sets the links of the previous and next items  |
| depending on the active filter (e.g. "Done", "In Progress", "Not Done").          |
=====================================================================================
*/
function setPrevAndNextLink() {
    // Get current filter of current upgrade.
    let filter = localStorage.getItem(`filter-${from_version}-${to_version}`);

    // Construct dict for API call.
    let data = {
        from_version: from_version,
        to_version: to_version,
        mitre_id: mitre_id,
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

/*
=====================================================================================
| This function gets and sets the currently active filter from LocalStorage.        |
=====================================================================================
*/
function showCurrentFilter() {
    let filter = localStorage.getItem(`filter-${from_version}-${to_version}`);
    
    // Default is "All".
    if (filter === null) {
        filter = "All";
    }

    $("#filter").html(`<b>Filter</b>: ${filter}`);
}



/*
=====================================================================================
| This function changes the evaluation status in the backend.                       |
=====================================================================================
*/
function setEventListenerEvaluationStatus() {
    $(".evaluation-status-select").on("change", function() {
        const target = $(this).attr("name"); // e.g. Client/Infra/Service Evaluation Status
        const value = $(this).val(); // e.g. evaluated, not evaluated, partial, ...
        
        const data = {
            from_version: from_version,
            to_version: to_version,
            mitre_id: mitre_id,
            target: target,
            value: value
        }

        $.ajax({
            url: url_evaluation_status,
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify(data)
        })
    });
}



/*
=====================================================================================
| This function saves the measures or the reasoning to the backend and displays a   |
| message if successful.                                                            |
=====================================================================================
*/
function setEventListenerReasoningAndMeasures() {
    $(".measures-button, .reasoning-button").on("click", function() {
        // Get the nearest textarea to the button.
        textarea = $(this).siblings("textarea");

        // Get the text.
        text = textarea.val();
        target = textarea.attr("name"); // e.g. Client/Infra/Service Measures/Reasoning

        // Get <span> element for status message.
        const message_element = $(this).siblings("span.message");

        const data = {
            from_version: from_version,
            to_version: to_version,
            mitre_id: mitre_id,
            target: target,
            text: text
        }

        $.ajax({
            url: url_change_reasoning_and_measures,
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify(data),
            success: function(response) {
                // Show message for 2 seconds in color (success=green).
                message_element.removeClass("error");
                message_element.addClass("success");
                message_element.text(response.message);
                setTimeout(() => { message_element.text(""); }, 2000);
            }
        });
    });
}


/*
=====================================================================================
| Sets and saves the state (expanded or not expanded) of the collapsable assessment |
| container. By default the container is not expanded.                              |
=====================================================================================
*/
function toggleAssessmentContainer() {
    assessment_container = $("#assessment");
    toggle_element = $("#toggle-assessment");

    // Restore.
    is_expanded = localStorage.getItem("expanded") === "true";
    if (is_expanded) {
        assessment_container.addClass("show");
        toggle_element.attr("aria-expanded", "true");
    }

    // Save changes on click.
    $("#toggle-assessment").on("click", function() {
        expanded = $(this).attr("aria-expanded");
        localStorage.setItem("expanded", expanded);
    });
}



setEventListenerDiffButton();
setEventListenerClassification();
setPrevAndNextLink();
showCurrentFilter();
setEventListenerEvaluationStatus();
setEventListenerReasoningAndMeasures();
toggleAssessmentContainer();