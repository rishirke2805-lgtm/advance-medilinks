// Optional client-side validation and form handling
document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('form');
  if (!form) return;

  form.addEventListener('submit', (e) => {
    const email = document.getElementById('email');
    if (email && email.value) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email.value.trim())) {
        alert('Please enter a valid email address.');
        email.focus();
        e.preventDefault();
      }
    }
  });
});
