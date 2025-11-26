function checkAndChangeTitle() {
    const currentTitle = document.title;

    if (currentTitle !== "Kojto") {
        document.title = "Kojto";
    }

    console.log("Final title:", document.title);
}

// Check if the observer variable is already declared
if (typeof observer === 'undefined') {
    // Set up a MutationObserver to watch for title changes
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            // Check if the target is the title element
            if (mutation.target.nodeName === 'TITLE') {
                checkAndChangeTitle();
            }
        });
    });

    // Start observing the title element for changes
    observer.observe(document.querySelector('title'), {
        childList: true // Listen for changes to child nodes (the title text)
    });
}