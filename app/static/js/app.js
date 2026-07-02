// Ozon ERP — Minimal frontend JS
// HTMX handles most interactivity; Alpine.js for dropdowns/menus.

document.addEventListener('alpine:init', () => {
    // Alpine component initialization if needed
});

// Auto-dismiss flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
    const flashes = document.querySelectorAll('[class*="bg-green-100"], [class*="bg-red-100"]');
    flashes.forEach(el => {
        setTimeout(() => {
            el.style.transition = 'opacity 0.5s';
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 500);
        }, 5000);
    });
});
