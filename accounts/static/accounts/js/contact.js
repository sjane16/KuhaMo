// Placeholder interaction only: no requests, storage, or message delivery.
(() => {
    const form = document.getElementById('contact-form');
    if (!form) return;
    const feedback = document.getElementById('contact-feedback');
    const fields = [...form.querySelectorAll('input, textarea')];
    const messages = {
        'contact-name': 'Please enter your full name.',
        'contact-email': 'Please enter a valid email address.',
        'contact-message': 'Please enter your message.',
    };

    function validate(field) {
        let message = '';
        if (field.required && !field.value.trim()) message = messages[field.id];
        else if (!field.validity.valid) message = messages[field.id] || 'Please check this field.';
        const error = document.getElementById(`${field.id}-error`);
        error.textContent = message;
        error.hidden = !message;
        field.setAttribute('aria-invalid', String(Boolean(message)));
        return !message;
    }

    fields.forEach(field => {
        const error = document.createElement('p');
        error.id = `${field.id}-error`;
        error.className = 'field-error';
        error.hidden = true;
        field.after(error);
        field.setAttribute('aria-describedby', error.id);
        field.addEventListener('input', () => {
            feedback.hidden = true;
            if (field.getAttribute('aria-invalid') === 'true') validate(field);
        });
    });

    form.addEventListener('submit', event => {
        event.preventDefault();
        const invalid = fields.filter(field => !validate(field));
        if (invalid.length) {
            feedback.hidden = true;
            invalid[0].focus();
            return;
        }
        feedback.textContent = 'Message delivery is currently unavailable. Your message has not been sent. Please try again later.';
        feedback.hidden = false;
        feedback.focus();
    });
})();
