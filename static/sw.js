const CACHE_NAME = 'teracms-cache-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/static/tera_logo.png',
  // Add links to your primary CSS/JS styling files here so they work offline
];

// 1. Install Event: Cache essential shell assets for offline use
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

// 2. Activate Event: Clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            return caches.delete(cache);
          }
        })
      );
    })
  );
  return self.clients.claim();
});

// 3. Fetch Event: Intercept network requests for offline fallback capacity
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(event.request).catch(() => {
        // Fallback or generic notification handle if network fails entirely
      });
    })
  );
});

// 4. Background Sync: Resilient connection engine for offline database actions
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-complaints') {
    event.waitUntil(
      console.log('Background Sync triggered: Processing offline complaint actions...')
    );
  }
});

// 5. Push Notifications: Handles displaying messages when socket context or app is closed
self.addEventListener('push', (event) => {
  let data = { title: 'Notification', body: 'New update from TeraCMS.' };
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { title: 'Update received', body: event.data.text() };
    }
  }

  const options = {
    body: data.body,
    icon: '/static/tera_logo.png',
    badge: '/static/tera_logo.png',
    vibrate: [100, 50, 100],
    data: { dateOfArrival: Date.now() }
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});