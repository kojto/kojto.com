function saveRecord() {
    var saveButton = document.querySelector(".o_form_button_save");
    if (saveButton) {
        saveButton.click();
    } else {
        console.warn("No button with class 'o_form_button_save' found.");
    }
}

setInterval(saveRecord, 500);
