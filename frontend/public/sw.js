// FARA CRM - Service Worker for Web Push notifications

self.addEventListener('push', event => {
  let data = { title: 'FARA CRM', body: '', url: '/chat' };
  try {
    data = event.data ? event.data.json() : data;
  } catch (e) {
    data.body = event.data ? event.data.text() : '';
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: data.icon || '/icon-192.png',
      badge: data.badge || '/badge-72.png',
      data: { url: data.url || '/chat' },
      tag: 'fara-' + Date.now(),
      renotify: true,
    }),
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then(windowClients => {
        for (const client of windowClients) {
          if (
            client.url.includes(self.registration.scope) &&
            'focus' in client
          ) {
            client.postMessage({ type: 'navigate', url: url });
            return client.focus();
          }
        }
        return clients.openWindow(url);
      }),
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(self.clients.claim());
});
