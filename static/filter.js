/*
=====================================================================================
| Important variables taken from the element with id "data".                        |
=====================================================================================
*/
const from_version = $("#data").data("from-version");
const to_version = $("#data").data("to-version");


// Set EventListener on the filter buttons.


/*
=====================================================================================
| Sets an EventListener on the Filter buttons. If a filter is activated (e.g. all   |
| changes that are "Done") all other changes are hidden.                            |
=====================================================================================
*/
function setEventListenerFilter() {
    $('input[name="btnradio"]').on("click", function() {
        const id = $(this).attr("id");
        const label_text = $(`label[for=${id}]`).text();
        
        // If "All" show all <tr> elements of all the changes.
        if (label_text == "All") {
            $(".status-select").each(function() {
                $(this).closest("tr").show();
            });

        // If anything else, hide the <tr> elements of the changes that are excluded by the filter.
        } else {
            $(".status-select").each(function() {
                if ($(this).val() === label_text) {
                    $(this).closest("tr").show();
                } else {
                    $(this).closest("tr").hide();
                }
            });
        }

        // Save the filter for the current upgrade in LocalStorage.
        localStorage.setItem(`filter-${from_version}-${to_version}`, label_text);
    });
}



/*
=====================================================================================
| Gets and restores the current filter on site reload.                              |
=====================================================================================
*/
function restoreFilter() {
    // Get the current filter from LocalStorage.
    let filter = localStorage.getItem(`filter-${from_version}-${to_version}`);

    // If filter is "All" or no filter is set, show everything.
    if (filter == "All" || !filter) {
        $(".status-select").each(function() {
            $(this).closest("tr").show();
        });
    
    // Else, activate the filter by hiding all elements that are excluded by the filter.
    } else {
        $(".status-select").each(function() {
            if ($(this).val() === filter) {
                $(this).closest("tr").show();
            } else {
                $(this).closest("tr").hide();
            }
        });
    }

    // Check/Uncheck the radio buttons.
    if (filter == "All" || !filter) {
        $("#btnradio1").prop("checked", true);
    } else if (filter == "Done") {
        $("#btnradio2").prop("checked", true);
    } else if (filter == "In Progress") {
        $("#btnradio3").prop("checked", true);
    } else if (filter == "Not Done") {
        $("#btnradio4").prop("checked", true);
    }
}



setEventListenerFilter();
restoreFilter();