/*
=====================================================================================
| This function handles the upload of the .ods/.xlsx file and sends it to the       |
| backend.                                                                          |
=====================================================================================
*/
function handleFileUpload() {
    let file_input = $("#file-input");
    let file_upload_url = $("#data").data("url-file-upload");

    $("#upload-btn").on("click", function() {
        // Get the file from the file input field.
        let file = file_input.prop("files")[0];
        
        if (!file) {
            alert("Select a file first");
            return;
        }
        
        // Create a FormData object that contains all necessary information and the file.
        const form_data = new FormData();
        form_data.append("file", file);
        form_data.append("from_version", from_version);
        form_data.append("to_version", to_version);

        // Send the file to backend.
        $.ajax({
            url: file_upload_url,
            type: "POST",
            data: form_data,
            processData: false,
            contentType: false,
            success: function(response) {
                $("#message").removeClass("alert-danger");
                $("#message").addClass("alert-primary");
                $("#message").show();
                $("#message-text").text(response.message);
            },
            error: function(xhr, status, error) {
                message = xhr.responseJSON.message;
                $("#message").removeClass("alert-primary");
                $("#message").addClass("alert-danger");
                $("#message").show();
                $("#message-text").text(message);
            }
        })
    });  
}



/*
=====================================================================================
| This function calls the export function in the backend. The backend creates a     |
| download URL that will be displayed for the user.                                 |
=====================================================================================
*/
function handleFileExport() {
    $("#export-btn").on("click", function() {
        let file_export_url = $("#data").data("url-file-export");
        const from_version = $("#data").data("from-version");
        const to_version = $("#data").data("to-version");
    
        const data = {
            from_version: from_version,
            to_version: to_version
        }
    
        $.ajax({
            url: file_export_url,
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify(data),
            dataType: "json",
            success: function(response) {
                $("#message").removeClass("alertDanger");
                $("#message").addClass("alert-primary");
                $("#message").show();
                $("#message-text").html(`
                    <p>
                        ${response.message}
                        <a href="${response.download_url}">Click here to download.</a>
                    </p>
                `);
            }
        })
    });
}



handleFileUpload();
handleFileExport();