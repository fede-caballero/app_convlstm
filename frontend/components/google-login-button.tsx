'use client'

import { useEffect, useRef } from 'react'
import { API_BASE_URL } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'

// Declare global google object
declare global {
    interface Window {
        google: any;
    }
}

export function GoogleLoginButton() {
    const { login } = useAuth()
    const buttonRef = useRef<HTMLDivElement>(null)
    const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || ""

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
            console.log("Backend response:", data)

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
        const initializeGoogle = () => {
            if (window.google && buttonRef.current) {
                window.google.accounts.id.initialize({
                    client_id: CLIENT_ID,
                    callback: handleCallback
                })
                window.google.accounts.id.renderButton(
                    buttonRef.current,
                    { theme: "outline", size: "large", width: "100%" }
                )
            }
        }

        // Check if script is already loaded
        if (window.google) {
            initializeGoogle()
            return
        }

        // Load Script if not present
        const script = document.createElement('script')
        script.src = "https://accounts.google.com/gsi/client"
        script.async = true
        script.defer = true
        script.onload = initializeGoogle
        document.body.appendChild(script)

        return () => {
            // Cleanup if needed
        }
    }, [])

    return <div ref={buttonRef} className="w-full mt-4"></div>
}
