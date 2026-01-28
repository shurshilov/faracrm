import { Button, Transition } from '@mantine/core';
import { IconCheck } from '@tabler/icons-react';
import { FormFieldsContext, useFormContext } from './FormContext';
import { useUpdateMutation } from '@/services/api/crudApi';
import { FaraRecord, Identifier } from '@/services/api/crudTypes';
import { Field } from '@/types/fields';
import { useContext, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { prepareValuesToSave } from './utils';
import { UseFormReturnType } from '@mantine/form';

type SaveState = 'idle' | 'saving' | 'success';

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
}: {
  model: string;
  id: Identifier;
  fields: Field[];
  parentId?: number;
  relatedFieldO2M?: string;
}) {
  const { t } = useTranslation('common');
  const { fields: fieldsServer } = useContext(FormFieldsContext);
  const form = useFormContext();
  const [update] = useUpdateMutation();
  const [saveState, setSaveState] = useState<SaveState>('idle');

  const handleSave = async () => {
    // Валидация обязательных полей
    if (!validateRequiredFields(form, fieldsServer)) {
      return; // Прерываем сохранение если есть ошибки
    }

    setSaveState('saving');

    try {
      const values = structuredClone(form.getValues());
      prepareValuesToSave(fieldsServer, values);
      const invalidateTags: string[] = [];

      await update({
        model,
        id,
        values,
        invalidateTags,
      });

      // Показываем галочку
      setSaveState('success');

      // Сбрасываем dirty state через задержку чтобы пользователь увидел галочку
      setTimeout(() => {
        const currentValues = form.getValues();
        form.resetDirty(currentValues);
        setSaveState('idle');
      }, 1200);
    } catch (error) {
      setSaveState('idle');
      // TODO: показать ошибку
    }
  };

  const getButtonText = () => {
    switch (saveState) {
      case 'saving':
        return t('saving');
      case 'success':
        return t('saved');
      default:
        return t('save');
    }
  };

  return (
    <Button
      loading={saveState === 'saving'}
      variant="filled"
      color={saveState === 'success' ? 'green' : undefined}
      leftSection={
        saveState === 'success' ? (
          <Transition mounted={true} transition="scale" duration={200}>
            {styles => <IconCheck size={18} style={styles} />}
          </Transition>
        ) : undefined
      }
      onClick={handleSave}
      disabled={saveState === 'success'}>
      {getButtonText()}
    </Button>
  );
}
