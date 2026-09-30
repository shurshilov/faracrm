/**
 * Реестр источников печати для кнопки «Печать» в тулбаре формы
 * (components/Form/PrintButton.tsx).
 *
 * Ядро рисует кнопку и меню, но не знает, что печатать: это подсказывают
 * модули. Провайдер — невидимый компонент: он делает свои запросы и проверки
 * прав для записи и отдаёт готовые пункты через onItems. Пока ни один
 * провайдер ничего не отдал, кнопки на форме нет.
 *
 * Регистрация — из fara_<модуль>/extensions.ts (грузится для всех моделей,
 * см. useModelExtensions):
 *   registerPrintProvider('report_docx', ReportPrintProvider);
 */
import { ComponentType, ReactNode, useSyncExternalStore } from 'react';

export interface PrintItem {
  key: string;
  label: string;
  icon?: ReactNode;
  /** Заголовок группы в меню; без группы — основной список */
  group?: string;
  onSelect: () => void;
}

export interface PrintProviderProps {
  model: string;
  recordId: number | string;
  /** Отдать пункты; ссылку на массив держать стабильной (useMemo) */
  onItems: (items: PrintItem[]) => void;
}

export type PrintProvider = ComponentType<PrintProviderProps>;

const providers = new Map<string, PrintProvider>();
const listeners = new Set<() => void>();
let snapshot: [string, PrintProvider][] = [];

/** Повторная регистрация под тем же ключом (Fast Refresh) заменяет. */
export function registerPrintProvider(
  key: string,
  provider: PrintProvider,
): void {
  providers.set(key, provider);
  snapshot = Array.from(providers.entries());
  listeners.forEach(listener => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Провайдеры печати; перерисовывает, если модуль зарегистрировался позже. */
export function usePrintProviders(): [string, PrintProvider][] {
  return useSyncExternalStore(subscribe, () => snapshot);
}
