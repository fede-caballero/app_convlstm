'use client'

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { subscribeToPushNotifications as subscribeAPI, unsubscribeFromPush as unsubscribeAPI } from './push-notifications'

export interface PushPreferences {
    alert_admin: boolean
    alert_proximity: boolean
    alert_aircraft: boolean
}

const DEFAULT_PREFS: PushPreferences = {
    alert_admin: true,
    alert_proximity: true,
    alert_aircraft: false
}

interface PushContextType {
    isSupported: boolean
    isSubscribed: boolean
    loading: boolean
    permissionStatus: string
    preferences: PushPreferences
    subscribe: () => Promise<boolean>
    unsubscribe: () => Promise<boolean>
    updatePreferences: (newPrefs: Partial<PushPreferences>) => Promise<boolean>
}

const PushContext = createContext<PushContextType | undefined>(undefined)

export function PushProvider({ children }: { children: ReactNode }) {
    const [isSubscribed, setIsSubscribed] = useState(false)
    const [loading, setLoading] = useState(false)
    const [isSupported, setIsSupported] = useState(false)
    const [permissionStatus, setPermissionStatus] = useState("checking")
    const [preferences, setPreferences] = useState<PushPreferences>(DEFAULT_PREFS)

    useEffect(() => {
        // Load preferences from local storage on mount
        const savedPrefs = localStorage.getItem('pushPreferences')
        if (savedPrefs) {
            try {
                setPreferences(JSON.parse(savedPrefs))
            } catch (e) {
                console.warn("Could not parse saved preferences")
            }
        }

        if (typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window) {
            setIsSupported(true)
            setPermissionStatus(Notification.permission)

            navigator.serviceWorker.ready.then(registration => {
                registration.pushManager.getSubscription().then(sub => {
                    if (sub) setIsSubscribed(true)
                })
            })
        } else {
            setPermissionStatus("unsupported")
        }
    }, [])

    const subscribe = async () => {
        setLoading(true)
        try {
            const apiPrefs = {
                alert_admin: preferences.alert_admin ? 1 : 0,
                alert_proximity: preferences.alert_proximity ? 1 : 0,
                alert_aircraft: preferences.alert_aircraft ? 1 : 0
            };
            const result = await subscribeAPI(apiPrefs)
            if (result) {
                setIsSubscribed(true)
                setPermissionStatus(Notification.permission)
                return true
            }
            return false
        } catch (error) {
            console.error(error)
            throw error
        } finally {
            setLoading(false)
        }
    }

    const unsubscribe = async () => {
        setLoading(true)
        try {
            const success = await unsubscribeAPI()
            if (success) {
                setIsSubscribed(false)
                return true
            }
            return false
        } catch (error) {
            console.error(error)
            return false
        } finally {
            setLoading(false)
        }
    }

    const updatePreferences = async (newPrefs: Partial<PushPreferences>) => {
        const merged = { ...preferences, ...newPrefs }
        setPreferences(merged)
        localStorage.setItem('pushPreferences', JSON.stringify(merged))

        if (isSubscribed) {
            setLoading(true)
            try {
                // Sending the new preferences updates the subscription entry silently
                const apiPrefs = {
                    alert_admin: merged.alert_admin ? 1 : 0,
                    alert_proximity: merged.alert_proximity ? 1 : 0,
                    alert_aircraft: merged.alert_aircraft ? 1 : 0
                };
                await subscribeAPI(apiPrefs)
                return true
            } catch (e) {
                console.error("Failed to sync preferences", e)
                return false
            } finally {
                setLoading(false)
            }
        }
        return true
    }

    return (
        <PushContext.Provider value={{ isSupported, isSubscribed, loading, permissionStatus, preferences, subscribe, unsubscribe, updatePreferences }}>
            {children}
        </PushContext.Provider>
    )
}

export function usePush() {
    const context = useContext(PushContext)
    if (context === undefined) {
        throw new Error('usePush must be used within a PushProvider')
    }
    return context
}
