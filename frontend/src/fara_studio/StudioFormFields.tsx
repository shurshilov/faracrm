/**
 * Поставщик полей формы ('provide:FormFields', модель '*'): поля зоны
 * «Дополнительно» — в запрос записи, обязательные из общих настроек формы —
 * звёздочкой и проверкой в кнопках. Без установленной студии сразу «готов»
 * и ничего не добавляет. Рисует поля зона (StudioZoneArea).
 */
import { useEffect } from 'react';
import type { FormFieldsProviderProps } from '@/components/Form/formFieldProviders';
import { useZone } from './useFormSettings';

export function StudioFormFields({
  model,
  layoutFields,
  onReport,
}: FormFieldsProviderProps) {
  const zone = useZone(model, layoutFields);

  useEffect(() => {
    onReport({
      ready: zone.ready,
      fields: zone.cells.map(cell => cell.name),
      required: zone.required,
    });
  }, [zone, onReport]);

  return null;
}
