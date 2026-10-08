/**
 * Поставщики полей формы — позиция 'provide:FormFields' (модель '*' — для
 * всех форм). Модуль добавляет форме поля в запрос записи (их нет в
 * разметке) и делает поля обязательными; форма грузит запись, когда все
 * поставщики готовы. Так студия добавляет поля своей зоны «Дополнительно».
 *
 * Поставщик — компонент: рендерится до загрузки записи, ничего не рисует и
 * сообщает о себе через onReport (свои хуки и запросы — как у любого
 * компонента). Рисует добавленные поля сам модуль — обёрткой разметки
 * формы ('wrap:Form').
 */
import {
  ComponentType,
  ReactNode,
  useCallback,
  useMemo,
  useState,
} from 'react';
import type { GetFormField } from '@/services/api/crudTypes';
import { getExtensionsForPosition } from '@/shared/extensions';

export interface FormFieldsReport {
  /** Поставщик знает, что добавить (его данные пришли). */
  ready: boolean;
  /** Поля к запросу записи. */
  fields: string[];
  /** Обязательные поля — звёздочка и проверка в кнопках формы. */
  required: string[];
}

export interface FormFieldsProviderProps {
  model: string;
  /** Поля, которые форма рисует сама: разметка и расширения. */
  layoutFields: string[];
  onReport: (report: FormFieldsReport) => void;
}

interface FormFieldProviders {
  ready: boolean;
  fields: string[];
  required: string[];
  /** Компоненты поставщиков — отрендерить в форме. */
  providers: ReactNode;
}

function sameReport(a: FormFieldsReport | undefined, b: FormFieldsReport) {
  return (
    !!a &&
    a.ready === b.ready &&
    a.fields.join() === b.fields.join() &&
    a.required.join() === b.required.join()
  );
}

/** Поставщики формы модели и сведённые их ответы. enabled — расширения
 *  модулей загружены (до этого реестр ещё пуст). */
export function useFormFieldProviders(
  model: string,
  layoutFields: string[],
  enabled: boolean,
): FormFieldProviders {
  const components: ComponentType<FormFieldsProviderProps>[] = enabled
    ? getExtensionsForPosition(model, 'provide:FormFields')
    : [];
  const [reports, setReports] = useState<Record<number, FormFieldsReport>>({});

  const report = useCallback((index: number, next: FormFieldsReport) => {
    setReports(prev =>
      sameReport(prev[index], next) ? prev : { ...prev, [index]: next },
    );
  }, []);
  // Колбэк на поставщика не меняется от рендера к рендеру.
  const reporters = useMemo(
    () =>
      components.map(
        (_, index) => (next: FormFieldsReport) => report(index, next),
      ),
    [components.length, report],
  );

  return useMemo(() => {
    const answered = components.map((_, index) => reports[index]);
    return {
      ready: answered.every(item => item?.ready),
      fields: [...new Set(answered.flatMap(item => item?.fields ?? []))],
      required: [...new Set(answered.flatMap(item => item?.required ?? []))],
      providers: components.map((Provider, index) => (
        <Provider
          key={index}
          model={model}
          layoutFields={layoutFields}
          onReport={reporters[index]}
        />
      )),
    };
    // components меняются только по длине (реестр дополняется загрузкой)
  }, [components.length, reports, reporters, model, layoutFields]);
}

/**
 * Проставить required полям — дальше работают штатные звёздочка и
 * проверка в кнопках «Создать»/«Сохранить».
 */
export function withRequired(
  fields: Record<string, GetFormField>,
  required: string[],
): Record<string, GetFormField> {
  if (!required.length) return fields;
  const result = { ...fields };
  for (const name of required) {
    if (result[name]) result[name] = { ...result[name], required: true };
  }
  return result;
}
