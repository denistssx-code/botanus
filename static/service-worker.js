// Ancien service worker remplacé par ce "nettoyeur" : il vide les caches de l'ancienne version
// (qui servait de vieilles pages), se désinscrit, puis recharge l'onglet une seule fois.
// La nouvelle interface n'utilise plus de service worker.
self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map(key => caches.delete(key)));
    await self.registration.unregister();
    const clients = await self.clients.matchAll({ type: 'window' });
    clients.forEach(client => client.navigate(client.url));
  })());
});
