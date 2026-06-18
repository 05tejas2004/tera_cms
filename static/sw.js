const CACHE_NAME = "teracms-v2";

const urlsToCache = [
    "/",
    "/login",
    "/dashboard",
    "/offline"
];

self.addEventListener("install", event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(urlsToCache))
    );
});

self.addEventListener("activate", event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.map(key => {
                    if (key !== CACHE_NAME) {
                        return caches.delete(key);
                    }
                })
            )
        )
    );
});

self.addEventListener("fetch", event => {
    event.respondWith(
        fetch(event.request)
            .then(response => {
                const copy = response.clone();

                caches.open(CACHE_NAME)
                    .then(cache => cache.put(event.request, copy));

                return response;
            })
            .catch(() => {
                return caches.match(event.request)
                    .then(response => {
                        return response || caches.match("/offline");
                    });
            })
    );
});