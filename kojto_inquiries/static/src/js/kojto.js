// Add active css
var spanText = document.querySelector('.o_last_breadcrumb_item.active span').textContent;
var links = document.querySelectorAll('a.o-dropdown-item.dropdown-item.o-navigable.o_nav_entry');

links.forEach(function(link) {
    if (link.textContent.trim() === spanText.trim()) {
        link.classList.add('currently_active');
    }
});