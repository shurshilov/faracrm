/**
 * Состояние режима студии — одно на приложение: включён ли режим и у
 * какой модели сейчас открыта форма. Форма сообщает о себе при
 * монтировании (StudioFormShell), переключатель в шапке (StudioToggle)
 * показывается, пока она открыта; ушли с формы — режим гаснет.
 */
import { useSyncExternalStore } from 'react';

interface StudioState {
  on: boolean;
  /** Модель открытой формы; null — формы нет. */
  model: string | null;
}

let state: StudioState = { on: false, model: null };
const listeners = new Set<() => void>();

function emit(next: StudioState) {
  state = next;
  listeners.forEach(listener => listener());
}

export function setStudioOn(on: boolean): void {
  if (state.on !== on) emit({ ...state, on });
}

export function setStudioForm(model: string | null): void {
  if (state.model === model) return;
  emit({ model, on: model ? state.on : false });
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useStudioMode(): StudioState {
  return useSyncExternalStore(subscribe, () => state);
}
