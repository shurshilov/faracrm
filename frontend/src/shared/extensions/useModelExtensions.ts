import { useEffect, useState } from 'react';
import { modelsConfig } from '@/config/models';

/**
 * Загружает модули-расширения модели (modelsConfig[model].extensions —
 * ленивые import()) и возвращает true, когда все они загружены для ЭТОЙ
 * модели.
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
