'use client'

import { useState, useEffect } from 'react'
import { AlertCircle, Edit, Send, X, Trash2, Bell, BellRing, BellOff, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { useAuth } from '@/lib/auth-context'
import { usePush } from '@/lib/push-context'
import { useLanguage } from "@/lib/language-context"

interface Comment {
    id: number
    content: string
    created_at: string
    author: string
}

export function AdminCommentBar() {
    const { t } = useLanguage()
    const { user, token } = useAuth()
    const [comments, setComments] = useState<Comment[]>([])
    const [visible, setVisible] = useState(true)
    const [newContent, setNewContent] = useState('')
    const [editingId, setEditingId] = useState<number | null>(null)
    const [editContent, setEditContent] = useState('')
    const [loading, setLoading] = useState(false)
    const [isOpen, setIsOpen] = useState(false) // Dropdown open state

    const { isSubscribed, isSupported, permissionStatus, subscribe, unsubscribe, loading: pushLoading } = usePush()

    const isAdmin = user?.role === 'admin'

    const fetchComments = async () => {
        try {
            // Admins get last 5 to manage, Users get last 5 to filter
            const res = await fetch('/api/comments?limit=5')
            if (res.ok) {
                const data: Comment[] = await res.json()
                setComments(data)
            }
        } catch (error) {
            console.error("Failed comments", error)
        }
    }

    useEffect(() => {
        fetchComments()
        const interval = setInterval(fetchComments, 10000)
        return () => clearInterval(interval)
    }, [])

    // Filter Logic
    const getVisibleComments = () => {
        if (isAdmin) return comments.slice(0, 3) // Admin sees top 3

        // User: Filter out old alerts (> 10 mins)
        const tenMinsAgo = new Date(Date.now() - 10 * 60 * 1000)
        return comments.filter(c => new Date(c.created_at) > tenMinsAgo)
    }

    const visibleComments = getVisibleComments()
    const hasActiveAlerts = visibleComments.length > 0;

    const handlePost = async () => {
        if (!newContent.trim()) return
        setLoading(true)
        try {
            await fetch('/api/comments', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ content: newContent })
            })
            setNewContent('')
            fetchComments()
        } finally { setLoading(false) }
    }

    const handleDelete = async (id: number) => {
        if (!confirm(t("¿Eliminar alerta?", "Delete alert?"))) return
        try {
            await fetch(`/api/comments/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            })
            fetchComments()
        } catch (e) { console.error(e) }
    }

    const handleUpdate = async (id: number) => {
        if (!editContent.trim()) return
        try {
            await fetch(`/api/comments/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ content: editContent })
            })
            setEditingId(null)
            fetchComments()
        } catch (e) { console.error(e) }
    }

    const handleTogglePush = async () => {
        try {
            if (isSubscribed) {
                const success = await unsubscribe()
                if (success) alert(t("Notificaciones desactivadas", "Notifications disabled"))
            } else {
                const result = await subscribe()
                if (result) alert(t("Notificaciones activadas", "Notifications enabled"))
            }
        } catch (e: any) {
            console.error(e)
            alert(t("Error: ", "Error: ") + (e.message || e))
        }
    }



    const [pushTitle, setPushTitle] = useState(t('Alerta Meteorológica', 'Weather Alert'))
    const [pushMessage, setPushMessage] = useState('')

    const handleSendPush = async () => {
        if (!pushMessage.trim()) return;
        setLoading(true)
        try {
            const res = await fetch('/api/notifications/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({
                    title: pushTitle,
                    message: pushMessage,
                    url: '/'
                })
            })
            if (res.ok) {
                setPushMessage('')
                alert(t("Notificación enviada con éxito", "Notification sent successfully"))
            } else {
                alert(t("Error al enviar notificación", "Error sending notification"))
            }
        } catch (e) {
            console.error(e)
            alert(t("Error de red", "Network error"))
        } finally {
            setLoading(false)
        }
    }


    // Interactive UI
    // Interactive UI
    return (
        <div className="pointer-events-auto">
            {/* 1. Toggle / Bell Trigger */}
            {(hasActiveAlerts || user) && (
                <Popover open={isOpen} onOpenChange={setIsOpen}>
                    <PopoverTrigger asChild>
                        <Button
                            variant="ghost"
                            className={`rounded-full shadow-lg backdrop-blur-md border border-white/20 h-9 transition-colors ${hasActiveAlerts
                                ? "bg-red-500/20 text-red-200 border-red-500/50 hover:bg-red-500/30"
                                : "bg-black/40 text-gray-300 hover:bg-white/10 hover:text-white"
                                }`}
                            size="sm"
                        >
                            <Bell className={`w-4 h-4 mr-2 ${hasActiveAlerts ? 'animate-pulse text-red-400' : ''}`} />
                            {t("Alertas", "Alerts")}
                            {hasActiveAlerts && <Badge variant="secondary" className="ml-2 h-5 min-w-[1.25rem] px-1 bg-red-500 text-white border-none">{visibleComments.length}</Badge>}
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-[340px] sm:w-[400px] p-0 bg-black/80 backdrop-blur-md border border-white/10 text-white shadow-2xl" align="center" side="bottom">
                        <div className="p-4 space-y-4">

                            {/* Header & Tabs */}
                            <div className="flex flex-col gap-2 border-b border-white/10 pb-2">
                                <div className="flex justify-between items-center">
                                    <h4 className="font-semibold text-lg">{t("Centro de Alertas", "Alert Center")}</h4>
                                    {isAdmin && <Badge variant="outline" className="text-xs border-white/20 text-white">Admin</Badge>}
                                </div>

                                {isAdmin && (
                                    <div className="mt-1">
                                        <p className="text-[10px] text-gray-400">
                                            {t("Tus comentarios se enviarán como Notificación Push a todos los usuarios.", "Your comments will be sent as a Push Notification to all users.")}
                                        </p>
                                    </div>
                                )}
                            </div>

                            {/* CONTENT: ALERTS TAB */}
                            <>

                                {/* ADMIN: Create New Alert */}
                                {isAdmin && (
                                    <div className="flex gap-2">
                                        <Input
                                            placeholder={t("Nueva alerta...", "New alert...")}
                                            value={newContent}
                                            onChange={e => setNewContent(e.target.value)}
                                            onKeyDown={e => { if (e.key === 'Enter') handlePost() }}
                                            className="h-8 bg-white/10 border-none text-white text-xs"
                                        />
                                        <Button size="sm" onClick={handlePost} disabled={loading} className="h-8 bg-blue-600 hover:bg-blue-700">
                                            <Send className="w-3 h-3" />
                                        </Button>
                                    </div>
                                )}

                                {/* List */}
                                <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1">
                                    {visibleComments.length === 0 ? (
                                        <p className="text-center text-sm text-gray-400 py-4">{t("No hay alertas activas recientes.", "No recent active alerts.")}</p>
                                    ) : (
                                        visibleComments.map(comment => (
                                            <div key={comment.id} className="relative bg-white/5 rounded-lg p-3 border-l-4 border-red-500">
                                                {editingId === comment.id ? (
                                                    <div className="flex flex-col gap-2">
                                                        <Input
                                                            value={editContent}
                                                            onChange={e => setEditContent(e.target.value)}
                                                            className="h-8 bg-black/40 text-white text-xs"
                                                        />
                                                        <div className="flex justify-end gap-2">
                                                            <Button size="icon" className="h-6 w-6 bg-green-600" onClick={() => handleUpdate(comment.id)}><Send className="w-3 h-3" /></Button>
                                                            <Button size="icon" className="h-6 w-6 bg-gray-600" onClick={() => setEditingId(null)}><X className="w-3 h-3" /></Button>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <>
                                                        <div className="flex justify-between items-start">
                                                            <span className="text-[10px] text-gray-400 font-mono">
                                                                {new Date(comment.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                            </span>
                                                            {isAdmin && (
                                                                <div className="flex gap-1">
                                                                    <button onClick={() => { setEditingId(comment.id); setEditContent(comment.content) }} className="text-gray-400 hover:text-white"><Edit className="w-3 h-3" /></button>
                                                                    <button onClick={() => handleDelete(comment.id)} className="text-red-400 hover:text-red-300"><Trash2 className="w-3 h-3" /></button>
                                                                </div>
                                                            )}
                                                        </div>
                                                        <p className="text-sm font-medium mt-1 leading-snug">{comment.content}</p>
                                                        <p className="text-[10px] text-gray-500 mt-1 text-right">{t("Autor:", "Author:")} {comment.author}</p>
                                                    </>
                                                )}
                                            </div>
                                        ))
                                    )}
                                </div>
                            </>




                            {/* FOOTER: Global Subscription (All Users) */}
                            {isSupported && (
                                <div className="pt-2 border-t border-white/10">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={async () => {
                                            if (!isSubscribed && Notification.permission === 'denied') {
                                                alert(t("Has bloqueado las notificaciones. Habilítalas en la configuración del navegador.", "You have blocked notifications. Enable them in your browser settings."))
                                                return;
                                            }
                                            await handleTogglePush()
                                        }}
                                        disabled={pushLoading}
                                        className={`w-full justify-between px-2 ${isSubscribed ? "text-green-400 hover:text-red-400 hover:bg-red-500/10" : "text-gray-400 hover:text-white"}`}
                                    >
                                        <span className="text-xs">
                                            {pushLoading ? t("Procesando...", "Processing...") : (isSubscribed ? t("Notificaciones Activas", "Notifications Enabled") : t("Activar Notificaciones", "Enable Notifications"))}
                                        </span>
                                        {isSubscribed ? <BellRing className="w-3 h-3" /> : <BellOff className="w-3 h-3" />}
                                    </Button>

                                    {!isSubscribed && (
                                        <div className="text-center mt-1">
                                            <p className="text-[10px] text-gray-500">
                                                {t("Recibe alertas de tormentas severas.", "Receive severe storm alerts.")}
                                            </p>
                                            <p className="text-[9px] text-gray-600 mt-1">
                                                {t("Estado:", "Status:")} {permissionStatus} | {t("Soporte:", "Support:")} {isSupported ? 'OK' : 'No'}
                                            </p>
                                        </div>
                                    )}
                                </div>
                            )}

                        </div>
                    </PopoverContent>
                </Popover>
            )}
        </div>
    )
}
