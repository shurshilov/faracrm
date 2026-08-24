// Copyright 2025 FARA CRM
// Локальная граница ошибок звонилки: если она упадёт при рендере, шапка и всё
// приложение остаются живыми (историю звонков и карточку клиента ведёт бэкенд).

import { Component, ReactNode } from 'react';

export class SipErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error('[sip] звонилка отключена из-за ошибки:', error);
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}
