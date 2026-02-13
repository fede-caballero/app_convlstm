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
    alert("Step 0: Start");
    if (!('serviceWorker' in navigator)) { alert("No SW support"); return; }

    alert("Step 1: Waiting for SW ready...");
    const registration = await navigator.serviceWorker.ready;
    alert("Step 2: SW Ready: " + registration.scope);

    try {
        // 1. Get Public Key from Backend
        alert("Step 3: Fetching Public Key...");
        const response = await fetch('/api/notifications/vapid-public-key');
        const data = await response.json();
        if (!data.publicKey) throw new Error("No public key returned");

        alert("Step 4: Got Key. Converting...");
        const convertedVapidKey = urlBase64ToUint8Array(data.publicKey);

        // 2. Subscribe using PushManager
        alert("Step 5: Calling pushManager.subscribe (Check permissions!)...");
        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: convertedVapidKey
        });

        alert("Step 6: Subscribe Local OK. Sending to Backend...");

        // 3. Send subscription to Backend
        // Fix: Use correct token storage (localStorage 'token' might be inside a JSON object if using context?)
        // Let's assume 'token' is key. If using provider, we might not have access here easily without passing it.
        // But let's try reading from localStorage which is where AuthProvider usually puts it.
        const token = localStorage.getItem('token');
        // Debug
        // alert("Token: " + (token ? "Found" : "Missing"));

        const subscribeResponse = await fetch('/api/notifications/subscribe', {
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

        alert("Step 7: Backend OK! Success!");
        console.log('Push subscription success');
        return true;
    } catch (error) {
        console.error('Push subscription failed:', error);
        alert("ERROR CRITICAL: " + error);
        throw error; // Re-throw to let UI handle the alert
    }
}
