const CACHE_NAME = 'bist-ai-v1';
const urlsToCache = [
  '/',
  '/static/favicon.ico'
];

// Service worker kurulumu
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

// Eski cache'leri temizle
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Network'ten cevap, yoksa cache'ten
self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Basit: her seferinde network'ten al
        return response;
      })
      .catch(() => {
        // Offline ise cache'ten al
        return caches.match(event.request);
      })
  );
});
