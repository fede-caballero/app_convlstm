"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import Link from "next/link"
import { API_BASE_URL } from "@/lib/api"
import { GoogleLoginButton } from "@/components/google-login-button"
import { LightningBackground } from "@/components/lightning-background"

export default function RegisterPage() {
    const [username, setUsername] = useState("")
    const [password, setPassword] = useState("")
    const [email, setEmail] = useState("")
    const [firstName, setFirstName] = useState("")
    const [lastName, setLastName] = useState("")

    const [error, setError] = useState("")
    const router = useRouter()

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError("")

        // Client-side Validation
        if (password.length < 8) {
            setError("La contraseña debe tener al menos 8 caracteres.")
            return
        }
        if (!/\d/.test(password) || !/[a-zA-Z]/.test(password)) {
            setError("La contraseña debe contener letras y números.")
            return
        }

        try {
            const res = await fetch(`${API_BASE_URL}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username,
                    password,
                    email,
                    first_name: firstName,
                    last_name: lastName,
                    role: 'viewer' // Default role
                })
            })

            if (res.ok) {
                // Auto login or redirect to login
                router.push('/login?registered=true')
            } else {
                const errData = await res.json()
                setError(errData.detail || "Error al registrarse")
            }
        } catch (error) {
            setError("Error de conexión con el servidor")
        }
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-zinc-950 p-4 font-sans text-zinc-100 relative overflow-hidden">
            <LightningBackground />
            <Card className="w-full max-w-md border-zinc-800 bg-zinc-900/80 backdrop-blur-md shadow-2xl z-10">
                <CardHeader className="space-y-1">
                    <div className="flex justify-center mb-4">
                        <img src="/logo.png" alt="Hailcast Logo" className="w-24 h-24 object-contain drop-shadow-[0_0_15px_rgba(255,255,255,0.3)]" />
                    </div>
                    <CardTitle className="text-2xl font-bold text-center text-white tracking-wide drop-shadow-md">Crear Cuenta</CardTitle>
                    <CardDescription className="text-center text-gray-200 font-medium">
                        Registrate para acceder al sistema
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <label className="text-sm font-bold text-white leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70" htmlFor="first-name">Nombre</label>
                                <Input id="first-name" placeholder="Juan" required
                                    value={firstName} onChange={(e) => setFirstName(e.target.value)}
                                    className="bg-zinc-800 border-zinc-700 text-zinc-100 focus:ring-primary focus:border-primary placeholder:text-zinc-500"
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-bold text-white leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70" htmlFor="last-name">Apellido</label>
                                <Input id="last-name" placeholder="Pérez" required
                                    value={lastName} onChange={(e) => setLastName(e.target.value)}
                                    className="bg-zinc-800 border-zinc-700 text-zinc-100 focus:ring-primary focus:border-primary placeholder:text-zinc-500"
                                />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-bold text-white leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70" htmlFor="email">Email</label>
                            <Input id="email" type="email" placeholder="m@ejemplo.com" required
                                value={email} onChange={(e) => setEmail(e.target.value)}
                                className="bg-zinc-800 border-zinc-700 text-zinc-100 focus:ring-primary focus:border-primary placeholder:text-zinc-500"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-bold text-white leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70" htmlFor="username">Usuario</label>
                            <Input id="username" placeholder="juanperez" required
                                value={username} onChange={(e) => setUsername(e.target.value)}
                                className="bg-zinc-800 border-zinc-700 text-zinc-100 focus:ring-primary focus:border-primary placeholder:text-zinc-500"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-bold text-white leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70" htmlFor="password">Contraseña</label>
                            <Input id="password" type="password" required
                                placeholder="••••••••"
                                value={password} onChange={(e) => setPassword(e.target.value)}
                                className="bg-zinc-800 border-zinc-700 text-zinc-100 focus:ring-primary focus:border-primary"
                            />
                            <p className="text-[10px] text-gray-400">Mínimo 8 caracteres, letras y números.</p>
                        </div>

                        {error && <div className="text-red-400 text-sm text-center bg-red-900/20 p-2 rounded border border-red-900/50">{error}</div>}

                        <Button type="submit" className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold shadow-lg shadow-primary/20">
                            Registrarse
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
                        ¿Ya tienes una cuenta?{" "}
                        <Link className="underline font-bold text-green-400 hover:text-green-300 transition-colors" href="/login">
                            Iniciar Sesión
                        </Link>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
