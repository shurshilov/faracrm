import { useEffect, useState } from 'react';
import { modelsConfig } from '@/config/models';

/**
 * Пользовательские модули frontend/src/business/<имя>/index.ts(x) — фронтовый
 * аналог автодискавера backend/business (*_ext.py): ядро о них не знает,
 * сборка подхватывает их глобом, а сами они регистрируют расширения через
 * registerExtension / registerFormTab. Правки core-файлов не нужны,
 * обновление ядра их не затирает. Ключи глоба Vite отдаёт отсортированными
 * по пути; папки нет — объект пустой. См. docs/dist/frontend/extensions.md.
 */
const businessModules = import.meta.glob([
  '../../business/*/index.ts',
  '../../business/*/index.tsx',
]);

/**
 * Загружает модули-расширения модели (modelsConfig[model].extensions —
 * ленивые import()) и business-модули; возвращает true, когда все они
 * загружены для ЭТОЙ модели.
 *
 * Пока модуль не загружен, его registerExtension() не выполнен, и
 * getExtensionFields(model) / getExtensionsFor*() отдают неполный набор.
 * Поэтому вью (Form, Kanban) ждут флаг перед запросом данных — иначе поля
 * расширений не попали бы в первый запрос и записи пришли бы без них.
 */
export function useModelExtensions(model: string): boolean {
  // Храним модель, для которой загрузка завершилась, а не булев флаг:
  // при смене model результат сам становится false без лишнего setState.
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const loadExtensions = async () => {
      const loaders = modelsConfig[model]?.extensions ?? [];
      await Promise.all(loaders.map(load => load()));
      // Business-модули — после модулей ядра и по одному в алфавитном
      // порядке папок: порядок регистрации детерминирован, их секции идут
      // после секций ядра на той же позиции, а replace:… перекрывает ядро.
      for (const load of Object.values(businessModules)) {
        await load();
      }
      if (!cancelled) {
        setLoadedFor(model);
      }
    };
    loadExtensions();
    return () => {
      cancelled = true;
    };
  }, [model]);

  return loadedFor === model;
}
