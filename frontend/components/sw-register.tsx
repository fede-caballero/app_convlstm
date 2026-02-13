'use client'

import { useEffect } from 'react'
import { registerServiceWorker } from '@/lib/push-notifications'

export function ServiceWorkerRegister() {
    useEffect(() => {
        registerServiceWorker()
    }, [])

    return null
}
