import type { TFunction } from 'i18next';
import { modelNamespace } from '@/config/modelNamespace';

/**
 * Подпись поля, у которого нет своей метки в разметке. Ищется в переводах
 * модуля модели (modelNamespace): блок модели (`leads:leads.name`), общий
 * блок полей модуля (`users:fields.name`), затем общие для всех моделей
 * поля (`common:fields.create_datetime` — аудит, вложения, активности);
 * иначе подпись из модели (Field.string), иначе техническое имя.
 */
export function fieldLabel(
  t: TFunction,
  model: string,
  field: { name: string; string?: string },
): string {
  const ns = modelNamespace(model);
  return t(
    [
      `${ns}:${model}.${field.name}`,
      `${ns}:fields.${field.name}`,
      `common:fields.${field.name}`,
    ],
    { defaultValue: field.string || field.name },
  );
}
