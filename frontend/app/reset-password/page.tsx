"use client"

import { useState, useEffect, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Eye, EyeOff } from "lucide-react"
import Link from "next/link"
import { API_BASE_URL } from "@/lib/api"
import { LightningBackground } from "@/components/lightning-background"

function ResetPasswordForm() {
    const [password, setPassword] = useState("")
    const [confirmPassword, setConfirmPassword] = useState("")
    const [showPassword, setShowPassword] = useState(false)
    const [error, setError] = useState("")
    const [message, setMessage] = useState("")
    const [loading, setLoading] = useState(false)

    const searchParams = useSearchParams()
    const token = searchParams.get('token')
    const router = useRouter()

    useEffect(() => {
        if (!token) {
            setError("Enlace inválido o expirado. Vuelve a solicitar la recuperación.")
        }
    }, [token])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError("")
        setMessage("")

        if (!token) {
            setError("Falta el token de seguridad.")
            return
        }

        if (password !== confirmPassword) {
            setError("Las contraseñas no coinciden.")
            return
        }

        if (password.length < 8 || !/\d/.test(password) || !/[a-zA-Z]/.test(password)) {
            setError("La contraseña debe tener al menos 8 caracteres, letras y números.")
            return
        }

        setLoading(true)
        try {
            const res = await fetch(`${API_BASE_URL}/auth/reset-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token, new_password: password })
            })

            const data = await res.json()

            if (res.ok) {
                setMessage("✅ " + data.message)
                setTimeout(() => {
                    router.push("/login")
                }, 3000)
            } else {
                setError("❌ " + (data.error || "Error al restablecer contraseña."))
            }
        } catch (err) {
            setError("❌ Error de conexión.")
        } finally {
            setLoading(false)
        }
    }

    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
                <label className="text-sm font-bold text-gray-200" htmlFor="password">Nueva Contraseña</label>
                <div className="relative">
                    <Input
                        id="password"
                        type={showPassword ? "text" : "password"}
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        disabled={!token || !!message}
                        className="bg-zinc-800 border-zinc-700 text-zinc-100 focus:ring-primary focus:border-primary pr-10"
                    />
                    <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
                        disabled={!token || !!message}
                    >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                </div>
            </div>

            <div className="space-y-2">
                <label className="text-sm font-bold text-gray-200" htmlFor="confirm-password">Confirmar Contraseña</label>
                <Input
                    id="confirm-password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    disabled={!token || !!message}
                    className="bg-zinc-800 border-zinc-700 text-zinc-100 focus:ring-primary focus:border-primary"
                />
            </div>

            {error && <div className="text-red-400 text-sm p-2 bg-red-900/20 border border-red-900/50 rounded-md text-center">{error}</div>}
            {message && <div className="text-green-400 text-sm p-2 bg-green-900/20 border border-green-900/50 rounded-md text-center">{message}</div>}

            <Button type="submit" disabled={!token || loading || !!message} className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold">
                {loading ? "Procesando..." : "Guardar Nueva Contraseña"}
            </Button>

            <div className="text-center mt-4">
                <Link href="/login" className="text-xs text-gray-400 hover:text-white underline transition-colors">
                    Volver al Inicio de Sesión
                </Link>
            </div>
        </form>
    )
}

export default function ResetPasswordPage() {
    return (
        <div className="min-h-screen flex items-center justify-center bg-zinc-950 p-4 font-sans text-zinc-100 relative overflow-hidden">
            <LightningBackground />
            <Card className="w-full max-w-md border-zinc-800 bg-zinc-900/80 backdrop-blur-md shadow-2xl z-10">
                <CardHeader className="space-y-1">
                    <CardTitle className="text-2xl font-bold text-center text-white">Restablecer Contraseña</CardTitle>
                    <CardDescription className="text-center text-gray-200 font-medium">
                        Ingresa tu nueva contraseña para continuar.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <Suspense fallback={<div className="text-center text-gray-400 py-4">Cargando...</div>}>
                        <ResetPasswordForm />
                    </Suspense>
                </CardContent>
            </Card>
        </div>
    )
}
