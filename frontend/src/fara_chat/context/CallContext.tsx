/**
 * CallContext — singleton-обёртка над useWebRTCCall.
 * Чтобы несколько компонентов (кнопка "Позвонить", overlay активного звонка,
 * модалка входящего) работали с ОДНИМ экземпляром state-машины, звонок
 * поднимается один раз на уровне приложения и шарится через контекст.
 *
 * Монтируй <CallProvider> один раз в корне (внутри ChatWebSocketProvider).
 */
import { createContext, useContext, ReactNode } from 'react';
import { useWebRTCCall, UseWebRTCCallResult } from '../hooks/useWebRTCCall';

const CallContext = createContext<UseWebRTCCallResult | null>(null);

export function CallProvider({ children }: { children: ReactNode }) {
  const call = useWebRTCCall();
  return <CallContext.Provider value={call}>{children}</CallContext.Provider>;
}

export function useCall(): UseWebRTCCallResult {
  const ctx = useContext(CallContext);
  if (!ctx) {
    throw new Error('useCall must be used within <CallProvider>');
  }
  return ctx;
}
