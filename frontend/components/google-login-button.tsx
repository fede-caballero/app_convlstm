'use client'

import { useEffect, useRef, useState } from 'react'
import { API_BASE_URL } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'

// Declare global google object
declare global {
    interface Window {
        google: any;
        _googleSigninInitialized?: boolean;
    }
}

export function GoogleLoginButton() {
    const { login } = useAuth()
    const buttonRef = useRef<HTMLDivElement>(null)
    const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || ""
    const [scriptError, setScriptError] = useState(false)

    const handleCallback = async (response: any) => {
        try {
            console.log("Sending credential to backend...")
            const res = await fetch(`${API_BASE_URL}/auth/google`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    credential: response.credential,
                    client_id: CLIENT_ID
                })
            })

            const data = await res.json()
            // console.log("Backend response:", data) // Security: Token hidden

            if (res.ok) {
                console.log("Login success, redirecting...")
                login(data.access_token, data.role, data.username)
            } else {
                console.error("Google Login Backend Error:", data.error)
            }
        } catch (e) {
            console.error("Google Login Network Error:", e)
        }
    }

    useEffect(() => {
        let isMounted = true;
        const initializeGoogle = () => {
            if (!isMounted) return;
            if (window.google && buttonRef.current) {
                if (!window._googleSigninInitialized) {
                    window.google.accounts.id.initialize({
                        client_id: CLIENT_ID,
                        callback: handleCallback
                    })
                    window._googleSigninInitialized = true
                }
                window.google.accounts.id.renderButton(
                    buttonRef.current,
                    { theme: "outline", size: "large" }
                )
            }
        }

        // Check if script is already loaded
        if (window.google) {
            initializeGoogle()
            return
        }

        const existingScript = document.querySelector('script[src="https://accounts.google.com/gsi/client"]') as HTMLScriptElement
        if (existingScript) {
            existingScript.addEventListener('load', initializeGoogle)
            existingScript.addEventListener('error', () => { if (isMounted) setScriptError(true) })
            // If already errored before we attached the listener, we might not catch it.
            return
        }

        // Load Script if not present
        const script = document.createElement('script')
        script.src = "https://accounts.google.com/gsi/client"
        script.async = true
        script.defer = true
        script.onload = initializeGoogle
        script.onerror = () => {
            if (isMounted) setScriptError(true)
        }
        document.body.appendChild(script)

        return () => {
            isMounted = false
            // Optional: prevent memory leaks or unwanted callbacks on unmount
        }
    }, [])

    if (scriptError) {
        return (
            <div className="w-full mt-4 p-3 bg-red-900/20 border border-red-500/30 rounded-lg text-center">
                <p className="text-xs text-red-200">
                    No se pudo cargar el inicio de sesión de Google.<br />
                    <span className="text-red-400 font-bold">Por favor desactivá tu bloqueador de anuncios para esta página.</span>
                </p>
            </div>
        )
    }

    return <div ref={buttonRef} className="w-full mt-4 flex justify-center"></div>
}
