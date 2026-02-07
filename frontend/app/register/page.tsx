"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import Link from "next/link"
import { API_BASE_URL } from "@/lib/api"
import { GoogleLoginButton } from "@/components/google-login-button"

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

        try {
            const res = await fetch(`${API_BASE_URL}/auth/register`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    username,
                    password,
                    email,
                    first_name: firstName,
                    last_name: lastName
                }),
            })

            const data = await res.json()

            if (!res.ok) {
                throw new Error(data.error || "Registration failed")
            }

            router.push('/login')
        } catch (err: any) {
            setError(err.message)
        }
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-background p-4">
            <Card className="w-full max-w-md border-border shadow-lg">
                <CardHeader className="space-y-1">
                    <CardTitle className="text-2xl font-bold text-center text-primary">Crear Cuenta</CardTitle>
                    <CardDescription className="text-center">
                        Regístrate para acceder al sistema
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid grid-cols-2 gap-2">
                            <div className="space-y-2">
                                <Input
                                    type="text"
                                    placeholder="Nombre"
                                    value={firstName}
                                    onChange={(e) => setFirstName(e.target.value)}
                                    className="bg-muted border-input"
                                />
                            </div>
                            <div className="space-y-2">
                                <Input
                                    type="text"
                                    placeholder="Apellido"
                                    value={lastName}
                                    onChange={(e) => setLastName(e.target.value)}
                                    className="bg-muted border-input"
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Input
                                type="text"
                                placeholder="Usuario"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                                className="bg-muted border-input"
                            />
                        </div>
                        <div className="space-y-2">
                            <Input
                                type="email"
                                placeholder="Correo Electrónico"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                                className="bg-muted border-input"
                            />
                        </div>
                        <div className="space-y-2">
                            <Input
                                type="password"
                                placeholder="Contraseña"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                className="bg-muted border-input"
                            />
                        </div>
                        {error && <p className="text-sm text-destructive text-center">{error}</p>}
                        <Button type="submit" className="w-full bg-primary hover:bg-primary/90 text-primary-foreground">
                            Registrarse
                        </Button>

                        <div className="relative flex justify-center text-xs uppercase">
                            <span className="bg-background px-2 text-muted-foreground">O continúa con</span>
                        </div>

                        <GoogleLoginButton />

                        <div className="text-center text-sm text-muted-foreground mt-4">
                            ¿Ya tienes cuenta?{" "}
                            <Link href="/login" className="text-primary hover:underline">
                                Inicia Sesión
                            </Link>
                        </div>
                    </form>
                </CardContent>
            </Card>
        </div>
    )
}
