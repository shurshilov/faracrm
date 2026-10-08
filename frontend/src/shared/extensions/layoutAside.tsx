/**
 * Боковая панель приложения справа (AppShell.Aside в ModernLayout) для
 * модулей. <LayoutAside> рендерит детей в неё порталом — по дереву React
 * они остаются там, где объявлены (контексты, DndContext студии), — и,
 * пока смонтирован, раскрывает её: основная область сужается на ширину
 * панели, шапка не перекрывается. Так панель студии не закрывает форму.
 */
import { ReactNode, useEffect, useSyncExternalStore } from 'react';
import { createPortal } from 'react-dom';

let node: HTMLElement | null = null;
let width = 0;
// Сколько LayoutAside смонтировано: закрылась вложенная — панель остаётся.
let opened = 0;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach(listener => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** ModernLayout: DOM-узел AppShell.Aside (callback ref). */
export function setLayoutAsideNode(next: HTMLElement | null): void {
  node = next;
  emit();
}

/** Ширина открытой панели; null — закрыта. */
export function useLayoutAsideWidth(): number | null {
  return useSyncExternalStore(subscribe, () => (opened > 0 ? width : null));
}

export function LayoutAside({
  width: asideWidth,
  children,
}: {
  width: number;
  children: ReactNode;
}) {
  const target = useSyncExternalStore(subscribe, () => node);

  useEffect(() => {
    opened += 1;
    width = asideWidth;
    emit();
    return () => {
      opened -= 1;
      emit();
    };
  }, [asideWidth]);

  return target ? createPortal(children, target) : null;
}
