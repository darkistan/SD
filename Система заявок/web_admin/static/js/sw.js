// Service Worker для Системи заявок PWA
// Плейсхолдер __APP_RELEASE__ підставляється сервером у маршруті /sw.js (app_version.APP_VERSION)
const APP_RELEASE = '__APP_RELEASE__';
const CACHE_NAME = 'tickets-system-' + APP_RELEASE.replace(/\./g, '-');
const SW_VERSION = APP_RELEASE;

// Подія install - виконується при встановленні service worker
self.addEventListener('install', function(event) {
    console.log('[Service Worker] Installing service worker version', SW_VERSION);
    // Вмикаємо service worker одразу після встановлення
    self.skipWaiting();
});

// Подія activate - виконується при активації service worker
self.addEventListener('activate', function(event) {
    console.log('[Service Worker] Activating service worker version', SW_VERSION);
    // Отримуємо контроль над всіма сторінками одразу
    event.waitUntil(clients.claim());
});

// Обробка повідомлень від клієнта
self.addEventListener('message', function(event) {
    console.log('[Service Worker] Received message:', event.data);
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

