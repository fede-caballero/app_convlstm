self.addEventListener('push', function (event) {
    console.log('[SW] Push Received', event);
    let data = { title: 'New Alert', body: 'Check app for details', url: '/' };

    try {
        if (event.data) {
            data = event.data.json();
        }
    } catch (e) {
        console.error('[SW] Error parsing push data', e);
        data.body = 'Raw: ' + (event.data ? event.data.text() : 'No data');
    }

    const options = {
        body: data.body,
        icon: data.icon || '/icon-192x192.png',
        badge: '/badge-72x72.png',
        vibrate: [100, 50, 100],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: '2',
            url: data.url || '/'
        }
    };

    console.log('[SW] Showing notification:', data.title, options);

    event.waitUntil(
        self.registration.showNotification(data.title, options)
            .catch(err => console.error('[SW] showNotification failed: ', err))
    );
});

self.addEventListener('notificationclick', function (event) {
    console.log('Notification click received.')
    event.notification.close()
    event.waitUntil(
        clients.openWindow(event.notification.data.url)
    )
})
