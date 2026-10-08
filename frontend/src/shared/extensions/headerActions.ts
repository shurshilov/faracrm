/**
 * Реестр иконок шапки от модулей (ModernLayout, перед колокольчиком).
 *
 * Ядро рисует шапку, но не знает, какие кнопки нужны модулям: студия
 * ставит сюда переключатель режима. Компонент сам решает, показываться ли
 * (права, установлен ли модуль, открыта ли форма) — ядро его просто
 * рендерит.
 *
 * Регистрация — из fara_<модуль>/extensions.ts (см. useModelExtensions):
 *   registerHeaderAction('studio', StudioToggle);
 */
import { ComponentType, useSyncExternalStore } from 'react';

const actions = new Map<string, ComponentType>();
const listeners = new Set<() => void>();
let snapshot: [string, ComponentType][] = [];

/** Повторная регистрация под тем же ключом (Fast Refresh) заменяет. */
export function registerHeaderAction(
  key: string,
  component: ComponentType,
): void {
  actions.set(key, component);
  snapshot = Array.from(actions.entries());
  listeners.forEach(listener => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Иконки шапки; перерисовывает, если модуль зарегистрировался позже. */
export function useHeaderActions(): [string, ComponentType][] {
  return useSyncExternalStore(subscribe, () => snapshot);
}
