'use client'

import { useState, useEffect } from 'react'
import { Bell, BellOff, BellRing } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"
import { subscribeToPushNotifications } from "@/lib/push-notifications"

export function PushSubscriptionButton() {
    const [isSubscribed, setIsSubscribed] = useState(false)
    const [loading, setLoading] = useState(false)
    const [isSupported, setIsSupported] = useState(false)
    const { toast } = useToast()

    useEffect(() => {
        // Check if supported on client side
        if ('serviceWorker' in navigator && 'PushManager' in window) {
            setIsSupported(true)

            navigator.serviceWorker.ready.then(registration => {
                registration.pushManager.getSubscription().then(subscription => {
                    if (subscription) {
                        setIsSubscribed(true)
                    }
                })
            })
        }
    }, [])

    // ... handleSubscribe ...

    if (!isSupported) return null;

    const handleSubscribe = async () => {
        setLoading(true)
        try {
            const result = await subscribeToPushNotifications()
            if (result) {
                setIsSubscribed(true)
                toast({
                    title: "Notificaciones Activas",
                    description: "Recibirás alertas de tormentas severas.",
                })
            } else {
                toast({
                    variant: "destructive",
                    title: "Error",
                    description: "No se pudo activar las notificaciones. Verifica los permisos.",
                })
            }
        } catch (error) {
            console.error(error)
        } finally {
            setLoading(false)
        }
    }

    // Check moved to useEffect to avoid SSR errors

    return (
        <Button
            variant="ghost"
            size="icon"
            onClick={handleSubscribe}
            disabled={isSubscribed || loading}
            title={isSubscribed ? "Notificaciones Activas" : "Activar Alertas"}
            className={isSubscribed ? "text-green-400" : "text-zinc-400 hover:text-white hover:bg-white/10"}
        >
            {loading ? (
                <Bell className="h-5 w-5 animate-pulse" />
            ) : isSubscribed ? (
                <BellRing className="h-5 w-5" />
            ) : (
                <BellOff className="h-5 w-5" />
            )}
        </Button>
    )
}
