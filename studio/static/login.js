const form = document.getElementById('login-form');
const errorBox = document.getElementById('login-error');
form.addEventListener('submit', async event => {
  event.preventDefault();
  const button = form.querySelector('button[type=submit]');
  button.disabled = true; button.textContent = 'Signing in…'; errorBox.textContent = '';
  try {
    const response = await fetch('/login', {method:'POST', credentials:'same-origin', headers:{'Accept':'application/json'}, body:new FormData(form)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Sign-in failed. Please reload and try again.');
    const session = await fetch('/api/status', {credentials:'same-origin', cache:'no-store'});
    if (!session.ok) throw new Error('Chrome did not retain the session cookie. Open this address directly in a regular tab and allow cookies for this site.');
    window.location.assign('/');
  } catch(error) {
    errorBox.textContent = error.message;
    button.disabled = false; button.textContent = 'Open studio →';
  }
});
