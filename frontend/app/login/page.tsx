"use client"

import { useState } from "react"
import { useAuth } from "@/lib/auth-context"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import Link from "next/link"
import { API_BASE_URL } from "@/lib/api"
import { LightningBackground } from "@/components/lightning-background"
import { GoogleLoginButton } from "@/components/google-login-button"
import { Eye, EyeOff } from "lucide-react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"

export default function LoginPage() {
    const [username, setUsername] = useState("")
    const [password, setPassword] = useState("")
    const [showPassword, setShowPassword] = useState(false)
    const [error, setError] = useState("")

    const [isForgotOpen, setIsForgotOpen] = useState(false)
    const [forgotEmail, setForgotEmail] = useState("")
    const [forgotMessage, setForgotMessage] = useState("")
    const [forgotLoading, setForgotLoading] = useState(false)

    const { login } = useAuth()

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError("")
        try {
            const res = await fetch(`${API_BASE_URL}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            })

            if (res.ok) {
                const data = await res.json()
                login(data.access_token, data.role, data.username)
            } else {
                const errData = await res.json()
                setError(errData.detail || "Error al iniciar sesión")
            }
        } catch (error) {
            setError("Error de conexión")
        }
    }

    const handleForgotPassword = async (e: React.FormEvent) => {
        e.preventDefault()
        setForgotLoading(true)
        setForgotMessage("")
        try {
            const res = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: forgotEmail })
            })
            if (res.ok) {
                setForgotMessage("✅ Si el correo está registrado, enviamos un link para restablecer tu contraseña.")
                setForgotEmail("")
            } else {
                setForgotMessage("❌ Error al procesar la solicitud.")
            }
        } catch (error) {
            setForgotMessage("❌ Error de red.")
        } finally {
            setForgotLoading(false)
        }
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-zinc-950 p-4 font-sans text-zinc-100 relative overflow-hidden">
            <LightningBackground />
            <Card className="w-full max-w-md border-zinc-800 bg-zinc-900/80 backdrop-blur-md shadow-2xl z-10">
                <CardHeader className="space-y-1">
                    <CardTitle className="text-2xl font-bold text-center text-white tracking-wide drop-shadow-md">Sistema Radar</CardTitle>
                    <div className="flex justify-center my-4">
                        <img src="/logo.png" alt="Hailcast Logo" className="w-32 h-32 object-contain drop-shadow-[0_0_15px_rgba(255,255,255,0.3)]" />
                    </div>
                    <CardDescription className="text-center text-gray-200 font-medium">
                        Ingresa tus credenciales para acceder
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <label className="text-sm font-bold text-gray-200 leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70" htmlFor="username">Usuario o Email</label>
                            <Input
                                id="username"
                                type="text"
                                placeholder="usuario o email"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                                className="bg-zinc-800/80 border-zinc-600 text-white focus:ring-primary focus:border-primary placeholder:text-gray-500 font-medium"
                            />
                        </div>
                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <label className="text-sm font-bold text-gray-200 leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70" htmlFor="password">Contraseña</label>
                                <button
                                    type="button"
                                    onClick={() => setIsForgotOpen(true)}
                                    className="text-xs text-primary hover:text-primary/80 transition-colors font-medium"
                                >
                                    ¿Olvidaste tu contraseña?
                                </button>
                            </div>
                            <div className="relative">
                                <Input
                                    id="password"
                                    type={showPassword ? "text" : "password"}
                                    placeholder="••••••••"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                    className="bg-zinc-800 border-zinc-700 text-zinc-100 focus:ring-primary focus:border-primary pr-10"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(!showPassword)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
                                >
                                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                </button>
                            </div>
                        </div>

                        {error && <div className="text-red-400 text-sm text-center bg-red-900/20 p-2 rounded border border-red-900/50">{error}</div>}

                        <Button type="submit" className="w-full bg-orange-400 text-black hover:bg-orange-500 font-semibold shadow-lg shadow-orange-500/20">
                            Iniciar Sesión
                        </Button>

                        <div className="relative my-4">
                            <div className="absolute inset-0 flex items-center">
                                <span className="w-full border-t border-zinc-700" />
                            </div>
                            <div className="relative flex justify-center text-xs uppercase">
                                <span className="bg-zinc-900 px-2 text-gray-300">O continuar con</span>
                            </div>
                        </div>

                        <GoogleLoginButton />
                    </form>

                    <div className="mt-4 text-center text-sm text-white">
                        ¿No tienes una cuenta?{" "}
                        <Link className="underline font-bold text-green-400 hover:text-green-300 transition-colors" href="/register">
                            Regístrate
                        </Link>
                    </div>
                </CardContent>
            </Card>

            {/* Forgot Password Modal */}
            <Dialog open={isForgotOpen} onOpenChange={setIsForgotOpen}>
                <DialogContent className="bg-zinc-900 border-zinc-800 text-white sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Recuperar Contraseña</DialogTitle>
                        <DialogDescription className="text-zinc-400">
                            Ingresa el correo electrónico asociado a tu cuenta. Te enviaremos un enlace seguro para restablecer tu contraseña.
                        </DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleForgotPassword} className="space-y-4 pt-4">
                        <Input
                            type="email"
                            placeholder="tu@email.com"
                            value={forgotEmail}
                            onChange={e => setForgotEmail(e.target.value)}
                            required
                            className="bg-zinc-800 border-zinc-700 text-white"
                        />
                        {forgotMessage && <p className="text-sm font-medium pt-1 text-center">{forgotMessage}</p>}
                        <Button type="submit" disabled={forgotLoading} className="w-full bg-primary hover:bg-primary/90 text-black">
                            {forgotLoading ? "Enviando..." : "Enviar Enlace de Recuperación"}
                        </Button>
                    </form>
                </DialogContent>
            </Dialog>

        </div>
    )
}
