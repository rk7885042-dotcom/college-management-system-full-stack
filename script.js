document.addEventListener("DOMContentLoaded", () => {
  // Small client-side enhancement: automatically focus the search field on the students page.
  const search = document.querySelector('input[name="q"]');
  if (search && window.location.pathname === "/students") {
    // Do not autofocus on mobile to avoid opening the keyboard unexpectedly.
    if (window.innerWidth > 700) search.focus();
  }
});
