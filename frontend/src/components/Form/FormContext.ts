import { createFormContext } from '@mantine/form';
import { FaraRecord, GetFormField } from '@/services/api/crudTypes';
import { createContext, useContext, Dispatch, SetStateAction } from 'react';

// Form context для работы с формой
export const [FormProvider, useFormContext] = createFormContext<FaraRecord>();

// Объединённый контекст для полей и модели
export interface FormFieldsContextType {
  model: string;
  fields: Record<string, GetFormField>;
  /** Функция для обновления полей (для динамических расширений) */
  setFields?: Dispatch<SetStateAction<Record<string, GetFormField>>>;
  /** Обработчик изменения поля с поддержкой onchange */
  handleFieldChange?: (fieldName: string, value: any) => Promise<void>;
  /** Поля с onchange обработчиками */
  onchangeFields?: string[];
}

export const FormFieldsContext = createContext<FormFieldsContextType>({
  model: '',
  fields: {},
});

// Хук для получения данных из контекста
export const useFormFields = () => useContext(FormFieldsContext);
