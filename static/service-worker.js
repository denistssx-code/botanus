const CACHE_NAME = 'botanus-v13-5';
const RUNTIME_CACHE = 'botanus-runtime';

// Fichiers à mettre en cache lors de l'installation
const PRECACHE_URLS = [
  '/',
  '/static/index.html',
  '/static/icon.svg'
];

// Installation - mise en cache des fichiers essentiels
self.addEventListener('install', event => {
  console.log('🌿 Service Worker: Installation...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('🌿 Service Worker: Mise en cache des fichiers');
        return cache.addAll(PRECACHE_URLS);
      })
      .then(() => self.skipWaiting())
  );
});

// Activation - nettoyage des anciens caches
self.addEventListener('activate', event => {
  console.log('🌿 Service Worker: Activation...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME && cacheName !== RUNTIME_CACHE) {
            console.log('🌿 Service Worker: Suppression ancien cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Stratégie de cache: Network First avec fallback
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Ignorer les requêtes non-HTTP
  if (!url.protocol.startsWith('http')) {
    return;
  }

  // Pour les requêtes API: toujours essayer le réseau d'abord
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Cloner la réponse pour la mettre en cache
          const responseClone = response.clone();
          caches.open(RUNTIME_CACHE).then(cache => {
            cache.put(request, responseClone);
          });
          return response;
        })
        .catch(() => {
          // Si le réseau échoue, chercher dans le cache
          return caches.match(request);
        })
    );
    return;
  }

  // Pour les fichiers statiques: Cache First
  event.respondWith(
    caches.match(request)
      .then(cachedResponse => {
        if (cachedResponse) {
          return cachedResponse;
        }

        return fetch(request).then(response => {
          // Ne pas mettre en cache les erreurs
          if (!response || response.status !== 200) {
            return response;
          }

          const responseClone = response.clone();
          caches.open(RUNTIME_CACHE).then(cache => {
            cache.put(request, responseClone);
          });

          return response;
        });
      })
  );
});

// Gestion des messages (pour futures fonctionnalités)
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

console.log('🌿 Service Worker: Chargé et prêt !');
