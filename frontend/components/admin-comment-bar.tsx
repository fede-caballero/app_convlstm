'use client'

import { useState, useEffect } from 'react'
import { AlertCircle, Edit, Send, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { useAuth } from '@/lib/auth-context' // Import auth hook

interface Comment {
    content: string
    created_at: string
    author: string
}

export function AdminCommentBar() {
    const { user, token } = useAuth() // Use context
    const [comment, setComment] = useState<Comment | null>(null)
    const [isEditing, setIsEditing] = useState(false)
    const [newContent, setNewContent] = useState('')
    const [isLoading, setIsLoading] = useState(false)

    // Check admin role from Context, not localStorage
    const isAdmin = user?.role === 'admin'

    const fetchLatestComment = async () => {
        try {
            const res = await fetch('/api/comments/latest')
            if (res.ok) {
                const data = await res.json()
                setComment(data)
            }
        } catch (error) {
            console.error("Failed to fetch comments", error)
        }
    }

    useEffect(() => {
        fetchLatestComment()
    }, [])

    const handlePost = async () => {
        if (!newContent.trim()) return

        setIsLoading(true)
        // Token comes from context

        try {
            const res = await fetch('/api/comments', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ content: newContent })
            })

            if (res.ok) {
                setNewContent('')
                setIsEditing(false)
                fetchLatestComment() // Refresh
            } else {
                alert("Error posting comment")
            }
        } catch (error) {
            console.error("Error posting", error)
        } finally {
            setIsLoading(false)
        }
    }

    // If no comment and not admin, show nothing
    if (!comment && !isAdmin) return null

    return (
        <div className="w-full max-w-4xl mx-auto mb-4 px-4 sticky top-4 z-50">
            {/* Active Alert Display */}
            {comment && (
                <Alert variant="destructive" className="bg-red-950/90 border-red-900 text-red-100 shadow-lg backdrop-blur-md animate-in fade-in slide-in-from-top-4">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle className="font-bold flex justify-between items-center">
                        ⚠️ Alerta Meteorológica
                        <span className='text-[10px] font-normal opacity-70'>
                            {new Date(comment.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • Por {comment.author}
                        </span>
                    </AlertTitle>
                    <AlertDescription className="mt-1 text-sm font-medium">
                        {comment.content}
                    </AlertDescription>
                </Alert>
            )}

            {/* Admin Controls */}
            {isAdmin && (
                <div className="mt-2 flex justify-end">
                    {!isEditing ? (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setIsEditing(true)}
                            className="bg-black/50 text-white border-white/20 hover:bg-white/10 text-xs backdrop-blur-sm"
                        >
                            <Edit className="w-3 h-3 mr-2" />
                            {comment ? 'Actualizar Alerta' : 'Publicar Alerta'}
                        </Button>
                    ) : (
                        <div className="flex gap-2 w-full max-w-md bg-black/80 p-2 rounded-lg border border-white/10 backdrop-blur-md shadow-xl">
                            <Input
                                placeholder="Escribe la alerta aquí..."
                                value={newContent}
                                onChange={(e) => setNewContent(e.target.value)}
                                className="bg-white/10 border-none text-white placeholder:text-white/50 focus-visible:ring-1 focus-visible:ring-white/30"
                                autoFocus
                            />
                            <Button
                                size="icon"
                                onClick={handlePost}
                                className="bg-green-600 hover:bg-green-700"
                                disabled={isLoading}
                            >
                                <Send className="w-4 h-4" />
                            </Button>
                            <Button
                                size="icon"
                                variant="ghost"
                                onClick={() => setIsEditing(false)}
                                className="hover:bg-white/10 text-white/70"
                            >
                                <X className="w-4 h-4" />
                            </Button>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
