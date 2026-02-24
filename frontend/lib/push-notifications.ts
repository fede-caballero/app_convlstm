// Utility functions for Push Notifications subscription management

const PUBLIC_KEY_ENDPOINT = '/api/notifications/vapid-public-key';
const SUBSCRIBE_ENDPOINT = '/api/notifications/subscribe';

// Utility to convert VAPID key
function urlBase64ToUint8Array(base64String: string) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

export async function registerServiceWorker() {
    if ('serviceWorker' in navigator && 'PushManager' in window) {
        try {
            const registration = await navigator.serviceWorker.register('/sw.js', {
                scope: '/'
            });
            console.log('Service Worker registered:', registration);
            return registration;
        } catch (error) {
            console.error('Service Worker registration failed:', error);
            return null;
        }
    }
    return null;
}

export async function subscribeToPushNotifications() {
    if (!('serviceWorker' in navigator)) {
        console.warn("No Service Worker support");
        return;
    }

    // Explicitly request permission first (Required for Firefox/Safari)
    let permission = Notification.permission;
    if (permission === 'default') {
        permission = await Notification.requestPermission();
    }

    if (permission !== 'granted') {
        throw new Error("Permission NOT granted.");
    }

    const registration = await navigator.serviceWorker.ready;

    try {
        // 1. Get Public Key from Backend
        const response = await fetch('/api/notifications/vapid-public-key');
        const data = await response.json();
        if (!data.publicKey) throw new Error("No public key returned");

        const convertedVapidKey = urlBase64ToUint8Array(data.publicKey);

        // 2. Subscribe using PushManager
        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: convertedVapidKey
        });

        // 3. Get User Location (Required for proximity alerts)
        const position = await new Promise<GeolocationPosition>((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            });
        }).catch(err => {
            console.warn("Could not get precise location for push subscription:", err);
            return null;
        });

        // 4. Send subscription to Backend
        const token = localStorage.getItem('token');

        const payload: any = { subscription };
        if (position) {
            payload.latitude = position.coords.latitude;
            payload.longitude = position.coords.longitude;
        }

        const subscribeResponse = await fetch('/api/notifications/subscribe', {
            method: 'POST',
            body: JSON.stringify(payload),
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {})
            }
        });

        if (!subscribeResponse.ok) {
            const errorData = await subscribeResponse.json();
            throw new Error(errorData.error || `Failed to subscribe: ${subscribeResponse.status}`);
        }

        console.log('Push subscription success');
        return true;
    } catch (error) {
        console.error('Push subscription failed:', error);
        throw error;
    }
}

export async function unsubscribeFromPush() {
    if (!('serviceWorker' in navigator)) return;
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();

    if (!subscription) return;

    // 1. Unsubscribe from Backend
    try {
        const token = localStorage.getItem('token');
        await fetch('/api/notifications/subscribe', {
            method: 'DELETE',
            body: JSON.stringify({ endpoint: subscription.endpoint }),
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {})
            }
        });
    } catch (e) {
        console.error("Backend unsubscribe failed", e);
        // Continue to local unsubscribe anyway
    }

    // 2. Unsubscribe locally (browser)
    await subscription.unsubscribe();
    console.log("Unsubscribed from Push");
    return true;
}
