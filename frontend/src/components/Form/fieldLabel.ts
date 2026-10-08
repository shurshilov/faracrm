import type { TFunction } from 'i18next';

/**
 * Подпись поля, у которого нет своей метки в разметке: перевод модуля
 * (`<модель>:fields.<имя>`), иначе подпись из модели (Field.string),
 * иначе техническое имя.
 */
export function fieldLabel(
  t: TFunction,
  model: string,
  field: { name: string; string?: string },
): string {
  return t(`${model}:fields.${field.name}`, {
    defaultValue: field.string || field.name,
  });
}
