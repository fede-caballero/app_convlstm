'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

interface Props {
    children?: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null,
        errorInfo: null
    };

    public static getDerivedStateFromError(error: Error): State {
        // Update state so the next render will show the fallback UI.
        return { hasError: true, error, errorInfo: null };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("Uncaught error:", error, errorInfo);
        this.setState({ error, errorInfo });
    }

    public render() {
        if (this.state.hasError) {
            return (
                <div className="flex flex-col items-center justify-center min-h-screen bg-black text-white p-6">
                    <div className="bg-zinc-900 border border-red-500/50 rounded-xl p-6 max-w-md w-full shadow-2xl">
                        <div className="flex items-center gap-3 mb-4">
                            <AlertTriangle className="h-8 w-8 text-red-500" />
                            <h1 className="text-xl font-bold text-red-500">Error de Aplicación</h1>
                        </div>

                        <p className="text-zinc-300 mb-4 text-sm">
                            Algo salió mal al cargar la aplicación en este dispositivo.
                            Por favor, envía una captura de pantalla de este mensaje al desarrollador.
                        </p>

                        <div className="bg-black/50 p-3 rounded-lg overflow-auto max-h-64 border border-white/10">
                            <p className="text-red-400 font-mono text-xs font-bold mb-2">
                                {this.state.error?.toString()}
                            </p>
                            {this.state.errorInfo && (
                                <pre className="text-zinc-500 font-mono text-[10px] whitespace-pre-wrap">
                                    {this.state.errorInfo.componentStack}
                                </pre>
                            )}
                        </div>

                        <button
                            onClick={() => window.location.reload()}
                            className="mt-6 w-full bg-white text-black font-bold py-2 rounded-lg hover:bg-zinc-200 transition-colors"
                        >
                            Recargar Página
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
