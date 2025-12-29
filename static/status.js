/*
=====================================================================================
| The following function sets an event listener on a <select> tag that let's users  |
| change the status of a change. The request is being sent via Ajax, so the site    |
| can be dynamically updated. If the request was successfull, the progress is       |
| updated (in percentage).                                                          |
=====================================================================================
*/
function setEventListenerStatusSelect() {
    $(".status-select").on("change", function() {
        const status = $(this).val();
        const category = $(this).data("category");
        const mitre_id = $(this).data("mitre-id");
        const url_status = $("#data").data("url-status");
        const from_version = $("#data").data("from-version");
        const to_version = $("#data").data("to-version");
        const change_category = $(this).data("change-category");
        console.log(change_category);

        const data = {
            from_version: from_version,
            to_version: to_version,
            category: category,
            mitre_id: mitre_id,
            status: status
        };
        console.log(data);

        // https://api.jquery.com/jQuery.ajax/
        $.ajax({
            url: url_status,
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

                if (change_category) {
                    updatePercentage(change_category);
                }
            }
        });
    });
}

/*
=====================================================================================
| Dynamically update and calculate the current progress.                            |
=====================================================================================
*/
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
    let change_category_done_count = 0;
    let change_category_count = 0;        
    $(`.status-select[data-change-category="${category}"]`).each(function() {
        if ($(this).val() === "Done") {
            change_category_done_count++;
        }
        change_category_count++;
    });
    let percentage_category = (change_category_done_count / change_category_count * 100).toFixed(2);
    $(`#status-${category}`).text(`Status: ${percentage_category}%`);
}

setEventListenerStatusSelect();