document.addEventListener("DOMContentLoaded", () => {
    // Automatically focus the search field on the students page
    const search = document.querySelector('input[name="q"]');

    if (search && window.location.pathname === "/students") {
        // Avoid opening the keyboard on mobile devices
        if (window.innerWidth > 700) {
            search.focus();
        }
    }
});
