// static/src/js/time_input_widget.js
/** @odoo-module **/


function setupTimeInputMask() {
    // Handle input masking for time fields
    document.addEventListener('input', function(e) {
        if (e.target.matches('.time-input-mask input')) {
            let value = e.target.value.replace(/\D/g, ''); // Remove non-digits
            if (value.length >= 3 && value.length <= 4) {
                e.target.value = value.slice(0, 2) + ':' + value.slice(2);
            } else if (value.length > 4) {
                e.target.value = value.slice(0, 2) + ':' + value.slice(2, 4);
            }
        }
    });

    // Handle keydown for better UX
    document.addEventListener('keydown', function(e) {
        if (!e.target.matches('.time-input-mask input')) return;

        const key = e.key; // modern API
        const controlKeys = [
            'Backspace','Delete','Tab','Escape','Enter',
            'ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'
        ];
        if (controlKeys.includes(key)) return;

        // Allow only digits
        if (!/^[0-9]$/.test(key)) {
            e.preventDefault();
            return;
        }

        // Limit to 5 chars (HH:MM), but allow replacing selected text
        const input = e.target;
        const selStart = input.selectionStart ?? 0;
        const selEnd = input.selectionEnd ?? 0;
        const replacing = selEnd > selStart;
        if (input.value.length >= 5 && !replacing) {
            e.preventDefault();
        }
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupTimeInputMask);
} else {
    setupTimeInputMask();
}
