'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'

type Language = 'es' | 'en'

interface LanguageContextType {
    language: Language
    setLanguage: (lang: Language) => void
    t: (esText: string, enText: string) => string
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined)

export function LanguageProvider({ children }: { children: ReactNode }) {
    const [language, setLanguageState] = useState<Language>('es')
    const [isMounted, setIsMounted] = useState(false)

    useEffect(() => {
        setIsMounted(true)
        const savedLang = localStorage.getItem('app_language') as Language
        if (savedLang === 'en' || savedLang === 'es') {
            setLanguageState(savedLang)
        }
    }, [])

    const setLanguage = (lang: Language) => {
        setLanguageState(lang)
        localStorage.setItem('app_language', lang)
    }

    const t = (esText: string, enText: string) => {
        if (!isMounted) return esText // Default to Spanish during SSR to prevent hydration mismatch
        return language === 'en' ? enText : esText
    }

    return (
        <LanguageContext.Provider value={{ language, setLanguage, t }}>
            {children}
        </LanguageContext.Provider>
    )
}

export function useLanguage() {
    const context = useContext(LanguageContext)
    if (context === undefined) {
        throw new Error('useLanguage must be used within a LanguageProvider')
    }
    return context
}
