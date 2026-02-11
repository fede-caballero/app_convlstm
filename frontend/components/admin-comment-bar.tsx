'use client'

import { useState, useEffect } from 'react'
import { AlertCircle, Edit, Send, X, Trash2, Bell, BellRing, BellOff, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { useAuth } from '@/lib/auth-context'

interface Comment {
    id: number
    content: string
    created_at: string
    author: string
}

export function AdminCommentBar() {
    const { user, token } = useAuth()
    const [comments, setComments] = useState<Comment[]>([])
    const [visible, setVisible] = useState(true)
    const [newContent, setNewContent] = useState('')
    const [editingId, setEditingId] = useState<number | null>(null)
    const [editContent, setEditContent] = useState('')
    const [loading, setLoading] = useState(false)
    const [isOpen, setIsOpen] = useState(false) // Dropdown open state

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
        if (!confirm("¿Eliminar alerta?")) return
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

    const [isSubscribed, setIsSubscribed] = useState(false)
    const [isSupported, setIsSupported] = useState(false)

    useEffect(() => {
        // Check sw support
        if ('serviceWorker' in navigator && 'PushManager' in window) {
            setIsSupported(true)
            navigator.serviceWorker.ready.then(registration => {
                registration.pushManager.getSubscription().then(sub => {
                    if (sub) setIsSubscribed(true)
                })
            })
        }
    }, [])

    const handleSubscribe = async () => {
        setLoading(true)
        try {
            // Import dynamically or assume it's valid
            const { subscribeToPushNotifications } = await import('@/lib/push-notifications')
            const result = await subscribeToPushNotifications()
            if (result) {
                setIsSubscribed(true)
                alert("Notificaciones activadas")
            } else {
                alert("No se pudo activar. Verifica permisos.")
            }
        } catch (e) { console.error(e) }
        finally { setLoading(false) }
    }


    const [activeTab, setActiveTab] = useState<'alerts' | 'push'>('alerts')
    const [pushTitle, setPushTitle] = useState('Alerta Meteorológica')
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
                alert("Notificación enviada con éxito")
            } else {
                alert("Error al enviar notificación")
            }
        } catch (e) {
            console.error(e)
            alert("Error de red")
        } finally {
            setLoading(false)
        }
    }


    // Interactive UI
    // Interactive UI
    return (
        <div className="pointer-events-auto">
            {/* 1. Toggle / Bell Trigger */}
            {(hasActiveAlerts || isAdmin) && (
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
                            Alertas
                            {hasActiveAlerts && <Badge variant="secondary" className="ml-2 h-5 min-w-[1.25rem] px-1 bg-red-500 text-white border-none">{visibleComments.length}</Badge>}
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-[340px] sm:w-[400px] p-0 bg-black/80 backdrop-blur-md border border-white/10 text-white shadow-2xl" align="center" side="bottom">
                        <div className="p-4 space-y-4">

                            {/* Header & Tabs */}
                            <div className="flex flex-col gap-2 border-b border-white/10 pb-2">
                                <div className="flex justify-between items-center">
                                    <h4 className="font-semibold text-lg">Centro de Alertas</h4>
                                    {isAdmin && <Badge variant="outline" className="text-xs border-white/20 text-white">Admin</Badge>}
                                </div>

                                {isAdmin && (
                                    <div className="flex gap-2 mt-1">
                                        <button
                                            onClick={() => setActiveTab('alerts')}
                                            className={`flex-1 text-xs py-1 rounded-md transition-colors ${activeTab === 'alerts' ? 'bg-white/20 text-white font-bold' : 'text-gray-400 hover:text-white'}`}
                                        >
                                            Comentarios
                                        </button>
                                        <button
                                            onClick={() => setActiveTab('push')}
                                            className={`flex-1 text-xs py-1 rounded-md transition-colors ${activeTab === 'push' ? 'bg-red-500/40 text-red-100 font-bold' : 'text-gray-400 hover:text-white'}`}
                                        >
                                            Notificaciones Push
                                        </button>
                                    </div>
                                )}
                            </div>

                            {/* CONTENT: ALERTS TAB */}
                            {activeTab === 'alerts' && (
                                <>
                                    {/* ADMIN: Create New Alert */}
                                    {isAdmin && (
                                        <div className="flex gap-2">
                                            <Input
                                                placeholder="Nueva alerta..."
                                                value={newContent}
                                                onChange={e => setNewContent(e.target.value)}
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
                                            <p className="text-center text-sm text-gray-400 py-4">No hay alertas activas recientes.</p>
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
                                                            <p className="text-[10px] text-gray-500 mt-1 text-right">Autor: {comment.author}</p>
                                                        </>
                                                    )}
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </>
                            )}

                            {/* CONTENT: PUSH TAB */}
                            {activeTab === 'push' && (
                                <div className="space-y-4 animate-in fade-in zoom-in-95 duration-200">
                                    <div className="bg-red-500/10 border border-red-500/20 p-3 rounded-md">
                                        <p className="text-xs text-red-200">
                                            <AlertCircle className="w-3 h-3 inline mr-1" />
                                            Esto enviará una notificación a <strong>todos</strong> los dispositivos suscritos.
                                        </p>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-xs text-gray-400">Título</label>
                                        <Input
                                            value={pushTitle}
                                            onChange={e => setPushTitle(e.target.value)}
                                            className="bg-white/5 border-white/10 text-white"
                                            placeholder="Ej: Alerta de Granizo"
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-xs text-gray-400">Mensaje</label>
                                        <Input
                                            value={pushMessage}
                                            onChange={e => setPushMessage(e.target.value)}
                                            className="bg-white/5 border-white/10 text-white"
                                            placeholder="Detalles de la alerta..."
                                        />
                                    </div>

                                    <Button
                                        onClick={handleSendPush}
                                        disabled={loading || !pushMessage}
                                        className="w-full bg-red-600 hover:bg-red-700"
                                    >
                                        {loading ? "Enviando..." : (
                                            <>
                                                <Send className="w-4 h-4 mr-2" />
                                                Enviar Notificación Push
                                            </>
                                        )}
                                    </Button>
                                </div>
                            )}

                            {/* FOOTER: Global Subscription (All Users) */}
                            {isSupported && (
                                <div className="pt-2 border-t border-white/10">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={handleSubscribe}
                                        disabled={isSubscribed || loading}
                                        className={`w-full justify-between px-2 ${isSubscribed ? "text-green-400" : "text-gray-400 hover:text-white"}`}
                                    >
                                        <span className="text-xs">
                                            {isSubscribed ? "Notificaciones Activas" : "Activar Notificaciones"}
                                        </span>
                                        {isSubscribed ? <BellRing className="w-3 h-3" /> : <BellOff className="w-3 h-3" />}
                                    </Button>
                                    {!isSubscribed && (
                                        <p className="text-[10px] text-gray-500 text-center mt-1">
                                            Recibe alertas de tormentas severas.
                                        </p>
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
