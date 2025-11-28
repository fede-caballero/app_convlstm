"use client"

import React, { createContext, useContext, useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { API_BASE_URL } from './api'

interface User {
    username: string
    role: string
}

interface AuthContextType {
    user: User | null
    token: string | null
    login: (token: string, role: string, username: string) => void
    logout: () => void
    isLoading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null)
    const [token, setToken] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const router = useRouter()

    useEffect(() => {
        const storedToken = localStorage.getItem('token')
        if (storedToken) {
            // Validate token with backend
            fetch(`${API_BASE_URL}/auth/me`, {
                headers: { Authorization: `Bearer ${storedToken}` }
            })
                .then(res => {
                    if (res.ok) return res.json()
                    throw new Error('Invalid token')
                })
                .then(data => {
                    setToken(storedToken)
                    setUser({ username: data.sub, role: data.role })
                })
                .catch(() => {
                    localStorage.removeItem('token')
                    setToken(null)
                    setUser(null)
                })
                .finally(() => setIsLoading(false))
        } else {
            setIsLoading(false)
        }
    }, [])

    const login = (newToken: string, role: string, username: string) => {
        localStorage.setItem('token', newToken)
        setToken(newToken)
        setUser({ username, role })
        router.push('/')
    }

    const logout = () => {
        localStorage.removeItem('token')
        setToken(null)
        setUser(null)
        router.push('/login')
    }

    return (
        <AuthContext.Provider value={{ user, token, login, logout, isLoading }}>
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    const context = useContext(AuthContext)
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider')
    }
    return context
}
