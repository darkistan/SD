// Theme toggle
(function() {
    const themeToggle = document.getElementById('theme-toggle');
    if (!themeToggle) return;
    
    const themeIcon = document.getElementById('theme-icon');
    const html = document.documentElement;
    const body = document.body;
    
    const savedTheme = localStorage.getItem('theme') || 'dark';
    html.setAttribute('data-bs-theme', savedTheme);
    body.setAttribute('data-bs-theme', savedTheme);
    updateIcon(savedTheme);
    
    themeToggle.addEventListener('click', function() {
        const currentTheme = html.getAttribute('data-bs-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        
        html.setAttribute('data-bs-theme', newTheme);
        body.setAttribute('data-bs-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateIcon(newTheme);
    });
    
    function updateIcon(theme) {
        if (!themeIcon) return;
        if (theme === 'dark') {
            themeIcon.classList.remove('bi-moon-stars-fill');
            themeIcon.classList.add('bi-sun-fill');
        } else {
            themeIcon.classList.remove('bi-sun-fill');
            themeIcon.classList.add('bi-moon-stars-fill');
        }
    }
})();

