'use client'

import { useState, useEffect } from 'react'
import { Bell, BellOff, BellRing } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"
import { usePush } from "@/lib/push-context"

export function PushSubscriptionButton() {
    const { isSubscribed, isSupported, loading, subscribe, unsubscribe } = usePush()
    const { toast } = useToast()

    if (!isSupported) return null;

    if (!isSupported) return null;

    const handleToggle = async () => {
        try {
            if (isSubscribed) {
                // Unsubscribe logic
                await unsubscribe()
                toast({
                    title: "Notificaciones Desactivadas",
                    description: "Ya no recibirás alertas en este dispositivo.",
                })
            } else {
                // Subscribe logic
                const result = await subscribe()
                if (result) {
                    toast({
                        title: "Notificaciones Activas",
                        description: "Recibirás alertas de tormentas severas.",
                    })
                } else {
                    toast({
                        variant: "destructive",
                        title: "Error",
                        description: "No se pudo activar. Verifica permisos.",
                    })
                }
            }
        } catch (error: any) {
            console.error(error)
            toast({
                variant: "destructive",
                title: "Error de Suscripción",
                description: error.message || "Ocurrió un problema desconocido.",
            })
        }
    }

    return (
        <Button
            variant="ghost"
            size="icon"
            onClick={handleToggle}
            disabled={loading}
            title={isSubscribed ? "Desactivar Notificaciones" : "Activar Alertas"}
            className={isSubscribed ? "text-green-400 hover:text-red-400 hover:bg-white/10" : "text-zinc-400 hover:text-white hover:bg-white/10"}
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
