'use client'

import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { useLanguage } from "@/lib/language-context"
import { Bell, Calendar } from "lucide-react"
import { AppNotification } from "@/lib/api"

interface NotificationsDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    notifications: AppNotification[]
    selectedId?: number | null
}

export function NotificationsDialog({
    open,
    onOpenChange,
    notifications,
    selectedId
}: NotificationsDialogProps) {
    const { t } = useLanguage()

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md bg-[#1c1c1e] text-white border-none shadow-2xl rounded-xl max-h-[85vh] flex flex-col p-4">
                <DialogHeader className="pb-4 border-b border-white/10 shrink-0">
                    <DialogTitle className="text-xl font-bold flex items-center gap-2">
                        <Bell className="h-5 w-5 text-sky-400" />
                        {t('Bandeja de Notificaciones', 'Notification Inbox')}
                    </DialogTitle>
                </DialogHeader>

                <div className="flex-1 -mx-4 px-4 overflow-y-auto mt-4">
                    {notifications.length === 0 ? (
                        <div className="text-center py-8 text-zinc-500 text-sm">
                            {t('No hay notificaciones recientes.', 'No recent notifications.')}
                        </div>
                    ) : (
                        <div className="space-y-4 pb-4">
                            {notifications.map((notif) => {
                                const isSelected = selectedId === notif.id;
                                let date;
                                // SQLite stores as UTC usually, but just in case, append Z if it looks like it lacks timezone
                                if (!notif.created_at.includes('Z') && !notif.created_at.includes('+')) {
                                    date = new Date(notif.created_at + 'Z');
                                } else {
                                    date = new Date(notif.created_at);
                                }

                                return (
                                    <div
                                        key={notif.id}
                                        className={`p-4 rounded-xl border transition-all ${isSelected ? 'bg-sky-500/10 border-sky-500/30 ring-1 ring-sky-500' : 'bg-[#2c2c2e] border-white/5'}`}
                                    >
                                        <div className="flex items-start justify-between mb-2 gap-2">
                                            <h3 className="font-bold text-sm leading-tight text-white drop-shadow-sm">{notif.title}</h3>
                                            <span className="flex-shrink-0 text-[10px] flex items-center gap-1 text-zinc-400 font-mono tracking-tighter bg-black/30 px-1.5 py-0.5 rounded">
                                                <Calendar className="w-3 h-3" />
                                                {date.toLocaleDateString()} {date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                            </span>
                                        </div>
                                        <p className="text-sm text-zinc-300 whitespace-pre-line leading-relaxed font-medium">
                                            {notif.body}
                                        </p>
                                    </div>
                                )
                            })}
                        </div>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    )
}
