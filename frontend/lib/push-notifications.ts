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
    if (!('serviceWorker' in navigator)) return;

    const registration = await navigator.serviceWorker.ready;

    try {
        // 1. Get Public Key from Backend
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}${PUBLIC_KEY_ENDPOINT}`);
        const data = await response.json();
        if (!data.publicKey) throw new Error("No public key returned");

        const convertedVapidKey = urlBase64ToUint8Array(data.publicKey);

        // 2. Subscribe using PushManager
        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: convertedVapidKey
        });

        // 3. Send subscription to Backend
        // Using simple fetch to avoid circular deps with large api libraries, or pass token if needed
        // Assuming auth context handles token elsewhere or we pass it here.
        // For now, let's just use fetch. If we need Auth, we need the token.
        const token = localStorage.getItem('token'); // Simplistic token retrieval

        const subscribeResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}${SUBSCRIBE_ENDPOINT}`, {
            method: 'POST',
            body: JSON.stringify({ subscription }),
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
        return false;
    }
}
