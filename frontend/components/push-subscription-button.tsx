'use client'

import { useState, useEffect } from 'react'
import { Bell, BellOff, BellRing } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"
import { usePush } from "@/lib/push-context"

export function PushSubscriptionButton({ onClick }: { onClick?: () => void }) {
    const { isSubscribed, isSupported, loading } = usePush()

    if (!isSupported) return null;

    return (
        <Button
            variant="ghost"
            size="icon"
            onClick={onClick}
            disabled={loading}
            title={isSubscribed ? "Configurar Notificaciones" : "Activar Notificaciones"}
            className={isSubscribed ? "text-green-400 hover:text-green-300 hover:bg-white/10" : "text-zinc-400 hover:text-white hover:bg-white/10"}
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
