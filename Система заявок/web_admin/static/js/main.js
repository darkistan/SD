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

// Дзвоник: polling кількості NEW заявок (для адміна)
(function() {
    const bell = document.getElementById('new-tickets-bell');
    if (!bell) return;

    const badge = document.getElementById('new-tickets-badge');
    const icon = document.getElementById('new-tickets-bell-icon');
    if (!badge || !icon) return;

    const POLL_MS = 7000;

    function applyCount(count) {
        const n = Number.isFinite(count) ? Math.max(0, Math.trunc(count)) : 0;
        if (n > 0) {
            badge.textContent = n > 99 ? '99+' : String(n);
            badge.classList.remove('d-none');
            icon.classList.remove('bi-bell');
            icon.classList.add('bi-bell-fill');
        } else {
            badge.textContent = '';
            badge.classList.add('d-none');
            icon.classList.remove('bi-bell-fill');
            icon.classList.add('bi-bell');
        }
    }

    let inFlight = false;
    async function poll() {
        if (inFlight) return;
        inFlight = true;
        try {
            const res = await fetch('/api/admin/new_tickets_count', { credentials: 'same-origin' });
            if (!res.ok) return;
            const data = await res.json();
            applyCount(Number(data?.new_tickets_count));
        } catch (e) {
            // Тихий fail: не ламаємо UI при тимчасових збоях
        } finally {
            inFlight = false;
        }
    }

    // Перший запит одразу + далі інтервал
    poll();
    window.setInterval(poll, POLL_MS);
})();
