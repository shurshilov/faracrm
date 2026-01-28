import { useCallback, useEffect, useRef } from 'react';
import { UseFormReturnType } from '@mantine/form';
import {
  useGetOnchangeFieldsQuery,
  useExecuteOnchangeMutation,
} from '@/services/api/crudApi';
import { FaraRecord, GetFormField } from '@/services/api/crudTypes';

/**
 * Хук для обработки onchange событий формы.
 *
 * При изменении полей, отмеченных декоратором @onchange на бэкенде,
 * автоматически вызывает API и обновляет связанные поля формы.
 *
 * @param model - Имя модели (например "chat_connector")
 * @param form - Форма из useForm
 * @param setFields - Функция для обновления fieldsServer (опционально)
 *
 * @example
 * const form = useForm({ ... });
 * const { handleFieldChange } = useOnchange('chat_connector', form);
 *
 * // В компоненте поля:
 * <FieldSelection
 *   name="type"
 *   onChange={(value) => handleFieldChange('type', value)}
 * />
 */
export const useOnchange = (
  model: string,
  form: UseFormReturnType<FaraRecord>,
  setFields?: (fields: Record<string, GetFormField>) => void,
) => {
  // Получаем список полей с onchange обработчиками
  const { data: onchangeData } = useGetOnchangeFieldsQuery(
    { model },
    { skip: !model },
  );

  // Мутация для выполнения onchange
  const [executeOnchange, { isLoading }] = useExecuteOnchangeMutation();

  // Поля с onchange обработчиками
  const onchangeFields = onchangeData?.fields || [];

  // Ref для предотвращения повторных вызовов
  const pendingRef = useRef<string | null>(null);

  /**
   * Проверить есть ли у поля onchange обработчик
   */
  const hasOnchange = useCallback(
    (fieldName: string) => {
      return onchangeFields.includes(fieldName);
    },
    [onchangeFields],
  );

  /**
   * Вызвать onchange обработчик для поля
   */
  const triggerOnchange = useCallback(
    async (fieldName: string, newValue?: any) => {
      if (!hasOnchange(fieldName)) {
        return;
      }

      // Предотвращаем повторные вызовы
      if (pendingRef.current === fieldName) {
        return;
      }
      pendingRef.current = fieldName;

      try {
        // Получаем текущие значения формы
        const currentValues = form.getValues();

        // Если передано новое значение - используем его
        const values = newValue !== undefined
          ? { ...currentValues, [fieldName]: newValue }
          : currentValues;

        const result = await executeOnchange({
          model,
          trigger_field: fieldName,
          values,
        }).unwrap();

        // Обновляем поля формы результатами onchange
        if (result.values && Object.keys(result.values).length > 0) {
          form.setValues(prev => ({
            ...prev,
            ...result.values,
          }));
        }

        // Обновляем схему полей (для динамических расширений)
        if (result.fields && setFields) {
          setFields(prev => ({
            ...prev,
            ...result.fields,
          }));
        }
      } catch (error) {
        console.error('Onchange error:', error);
      } finally {
        pendingRef.current = null;
      }
    },
    [model, form, hasOnchange, executeOnchange, setFields],
  );

  /**
   * Обработчик изменения поля.
   * Устанавливает значение и вызывает onchange если нужно.
   */
  const handleFieldChange = useCallback(
    async (fieldName: string, value: any) => {
      // Сначала устанавливаем значение
      form.setFieldValue(fieldName, value);

      // Затем вызываем onchange
      await triggerOnchange(fieldName, value);
    },
    [form, triggerOnchange],
  );

  return {
    /** Список полей с onchange обработчиками */
    onchangeFields,
    /** Проверить есть ли у поля onchange */
    hasOnchange,
    /** Вызвать onchange вручную */
    triggerOnchange,
    /** Обработчик изменения поля (setValue + onchange) */
    handleFieldChange,
    /** Флаг загрузки */
    isLoading,
  };
};
