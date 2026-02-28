'use client'

import { useState, useEffect } from 'react'
import { Settings } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"
import { usePush } from "@/lib/push-context"

export function PushSubscriptionButton({ onClick }: { onClick?: () => void }) {
    const { isSupported } = usePush()

    if (!isSupported) return null;

    return (
        <Button
            variant="ghost"
            size="icon"
            onClick={onClick}
            title={"Configuraciones"}
            className={"text-zinc-400 hover:text-white hover:bg-white/10"}
        >
            <Settings className="h-5 w-5" />
        </Button>
    )
}
