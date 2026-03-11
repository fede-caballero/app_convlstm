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
            className={"text-zinc-900 hover:text-black hover:bg-zinc-200/50 h-11 w-11 rounded-full"}
        >
            <Settings className="h-6 w-6 stroke-[2.5px]" />
        </Button>
    )
}
