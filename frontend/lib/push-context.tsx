'use client'

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { subscribeToPushNotifications as subscribeAPI, unsubscribeFromPush as unsubscribeAPI } from './push-notifications'

interface PushContextType {
    isSupported: boolean
    isSubscribed: boolean
    loading: boolean
    permissionStatus: string
    subscribe: () => Promise<boolean>
    unsubscribe: () => Promise<boolean>
}

const PushContext = createContext<PushContextType | undefined>(undefined)

export function PushProvider({ children }: { children: ReactNode }) {
    const [isSubscribed, setIsSubscribed] = useState(false)
    const [loading, setLoading] = useState(false)
    const [isSupported, setIsSupported] = useState(false)
    const [permissionStatus, setPermissionStatus] = useState("checking")

    useEffect(() => {
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
            const result = await subscribeAPI()
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

    return (
        <PushContext.Provider value={{ isSupported, isSubscribed, loading, permissionStatus, subscribe, unsubscribe }}>
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
