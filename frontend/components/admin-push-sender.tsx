'use client'

import { useState } from 'react'
import { Send, BellRing, Loader2 } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useToast } from "@/components/ui/use-toast"
import { useAuth } from "@/lib/auth-context"

export function AdminPushSender() {
    const [title, setTitle] = useState("Alerta Meteorológica")
    const [message, setMessage] = useState("")
    const [loading, setLoading] = useState(false)
    const { toast } = useToast()
    const { token } = useAuth()

    const handleSend = async () => {
        if (!message) return;
        setLoading(true)

        try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/notifications/send`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    title,
                    message,
                    url: '/' // Default to opening app root
                })
            })

            const data = await res.json()

            if (res.ok) {
                toast({
                    title: "Notificación enviada",
                    description: `Enviada a ${data.results?.length || 0} dispositivos.`,
                })
                setMessage("") // Clear message
            } else {
                throw new Error(data.error || "Error al enviar")
            }
        } catch (error: any) {
            toast({
                variant: "destructive",
                title: "Error de envío",
                description: error.message,
            })
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card className="bg-white/5 border-white/10 text-white mt-6">
            <CardHeader className="pb-2">
                <div className="flex justify-between items-center">
                    <CardTitle className="text-sm font-medium text-red-200">Enviar Alerta Push</CardTitle>
                    <BellRing className="h-4 w-4 text-red-400" />
                </div>
            </CardHeader>
            <CardContent className="space-y-3">
                <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Título</label>
                    <Input
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        className="bg-black/20 border-white/10 text-xs h-8"
                        placeholder="Ej: Alerta de Granizo"
                    />
                </div>
                <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Mensaje</label>
                    <Textarea
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        className="bg-black/20 border-white/10 text-xs min-h-[80px]"
                        placeholder="Escribe el mensaje de la alerta..."
                    />
                </div>
                <Button
                    onClick={handleSend}
                    disabled={loading || !message}
                    className="w-full bg-red-600 hover:bg-red-700 h-8 text-xs font-bold"
                >
                    {loading ? (
                        <>
                            <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                            Enviando...
                        </>
                    ) : (
                        <>
                            <Send className="mr-2 h-3 w-3" />
                            Enviar Notificación
                        </>
                    )}
                </Button>
            </CardContent>
        </Card>
    )
}
