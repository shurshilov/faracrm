import { Button } from '@mantine/core';
import { FormFieldsContext, useFormContext } from './FormContext';
import { useUpdateMutation } from '@/services/api/crudApi';
import { FaraRecord, Identifier } from '@/services/api/crudTypes';
import { Field } from '@/types/fields';
import { useContext, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { prepareValuesToSave } from './utils';
import { UseFormReturnType } from '@mantine/form';

/**
 * Валидирует обязательные поля формы
 * @returns true если валидация прошла, false если есть ошибки
 */
const validateRequiredFields = (
  form: UseFormReturnType<FaraRecord>,
  fieldsServer: Record<string, any>,
): boolean => {
  let hasErrors = false;
  const values = form.getValues();

  for (const [fieldName, fieldInfo] of Object.entries(fieldsServer)) {
    if (fieldInfo.required) {
      const value = values[fieldName];
      let error: string | null = null;

      // Проверяем на пустое значение
      if (value === null || value === undefined || value === '') {
        error = 'Обязательное поле';
      }
      // Для Many2one проверяем что есть id
      else if (fieldInfo.type === 'Many2one' && typeof value === 'object') {
        if (!value?.id) {
          error = 'Обязательное поле';
        }
      }

      if (error) {
        form.setFieldError(fieldName, error);
        hasErrors = true;
      } else {
        form.setFieldError(fieldName, null);
      }
    }
  }

  return !hasErrors;
};

export function ButtonUpdate({
  model,
  id,
  fields,
  parentId,
  relatedFieldO2M,
  onSaveSuccess,
}: {
  model: string;
  id: Identifier;
  fields: Field[];
  parentId?: number;
  relatedFieldO2M?: string;
  onSaveSuccess?: () => void;
}) {
  const { t } = useTranslation('common');
  const { fields: fieldsServer } = useContext(FormFieldsContext);
  const form = useFormContext();
  const [update] = useUpdateMutation();
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    // Валидация обязательных полей
    if (!validateRequiredFields(form, fieldsServer)) {
      return;
    }

    setSaving(true);

    try {
      const values = structuredClone(form.getValues());

      // Собираем имена M2M/O2M полей с изменениями для инвалидации кеша
      const invalidateTags: string[] = [];
      for (const key of Object.keys(values)) {
        if (key.startsWith('_')) {
          const v = values[key];
          if (v?.unselected?.length || v?.created?.length || v?.selected?.length) {
            invalidateTags.push(key.slice(1)); // '_role_ids' -> 'role_ids'
          }
        }
      }

      prepareValuesToSave(fieldsServer, values);

      await update({
        model,
        id,
        values,
        invalidateTags,
      });

      // Сбрасываем dirty — кнопка исчезнет, Toolbar покажет галочку
      const currentValues = form.getValues();
      form.resetDirty(currentValues);
      onSaveSuccess?.();
    } catch (error) {
      // TODO: показать ошибку
    } finally {
      setSaving(false);
    }
  };

  return (
    <Button
      loading={saving}
      variant="filled"
      onClick={handleSave}>
      {saving ? t('saving') : t('save')}
    </Button>
  );
}
