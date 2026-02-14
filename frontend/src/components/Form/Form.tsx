import {
  BaseQueryFn,
  TypedUseQueryHookResult,
} from '@reduxjs/toolkit/query/react';
import { useLocation, useParams } from 'react-router-dom';
import { useForm, UseFormReturnType } from '@mantine/form';

import {
  Children,
  isValidElement,
  useEffect,
  useMemo,
  useState,
  useCallback,
} from 'react';
import { Box, Drawer } from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import {
  useReadDefaultValuesQuery,
  useReadQuery,
} from '@/services/api/crudApi';
import {
  FaraRecord,
  ReadDefaultValuesParams,
  ReadDefaultValuesResult,
  ReadParams,
  ReadResult,
  GetFormField,
} from '@/services/api/crudTypes';
import { FormFieldsContext, FormProvider } from './FormContext';
import { FormSettingsProvider, LabelPosition } from './FormSettingsContext';
import { Field } from '@/types/fields';
import { getChildrenRecursive, getComponentsFromChildren } from './utils';
import { Toolbar } from './Toolbar';
import { useOnchange } from './hooks/useOnchange';
import { getExtensionFields, ExtensionsContext } from '@/shared/extensions';
import { modelsConfig } from '@/config/models';
import { FormPanelSide, PanelType } from './Panels';

/**
 * Генерирует функции валидации для обязательных полей
 */
const buildValidation = (fields: Record<string, GetFormField>) => {
  const validate: Record<string, (value: any) => string | null> = {};

  for (const [fieldName, fieldInfo] of Object.entries(fields)) {
    if (fieldInfo.required) {
      validate[fieldName] = (value: any) => {
        // Проверяем на пустое значение
        if (value === null || value === undefined || value === '') {
          return 'Обязательное поле';
        }
        // Для Many2one проверяем что есть id
        if (fieldInfo.type === 'Many2one' && typeof value === 'object') {
          if (!value.id) {
            return 'Обязательное поле';
          }
        }
        return null;
      };
    }
  }

  return validate;
};

export const Form = <RecordType extends FaraRecord>({
  model,
  isCreateForm,
  parentFieldName,
  parentForm,
  modalClose,
  children,
  parentId,
  relatedFieldO2M,
  labelPosition = 'left',
  labelWidth = 160,
  actions,
}: {
  model: string;
  isCreateForm?: boolean;
  parentFieldName?: string;
  parentForm?: UseFormReturnType<FaraRecord>;
  parentId?: number;
  relatedFieldO2M?: string;
  modalClose?: () => void;
  children: React.ReactNode;
  labelPosition?: LabelPosition;
  labelWidth?: number | string;
  actions?: React.ReactNode;
}) => {
  const { pathname } = useLocation();
  const [fieldsServer, setFieldsServer] = useState<
    Record<string, GetFormField>
  >({});
  const [childrenNew, setChildrenNew] = useState<React.ReactNode[]>([]);
  const { id } = useParams<{ id: string }>();
  isCreateForm =
    isCreateForm || id === undefined || pathname.includes('/create');
  // здесь проверить условие one2many и many2many
  // для добавления вложенных полей
  // форма отправляет список полей в запросе
  const fieldsClient = useMemo(() => {
    return (
      Children.map(children, field => {
        if (!isValidElement(field)) {
          // Игнорируем не элементы или элементы не Модели
          return {} as Field;
        }
        return { name: field.props.name, type: field.type.name } as Field;
      }) || []
    );
  }, [children]);

  // Загружаем модули-расширения из config (один раз)
  const [extensionsLoaded, setExtensionsLoaded] = useState(false);
  useEffect(() => {
    let cancelled = false;
    const loadExtensions = async () => {
      const config = modelsConfig[model];
      if (config?.extensions) {
        await Promise.all(config.extensions.map(load => load()));
      }
      if (!cancelled) {
        setExtensionsLoaded(true);
      }
    };
    loadExtensions();
    return () => {
      cancelled = true;
    };
  }, [model]);

  // Собираем список полей из children + из расширений
  const fieldsList = useMemo(() => {
    const childrenFields = getChildrenRecursive(children);
    // После загрузки расширений добавляем их поля
    if (extensionsLoaded) {
      const extensionFields = getExtensionFields(model);
      for (const field of extensionFields) {
        if (!childrenFields.includes(field)) {
          childrenFields.push(field);
        }
      }
    }
    return childrenFields;
  }, [children, model, extensionsLoaded]);

  const params = {
    model,
    id,
    fields: fieldsList,
  } as ReadParams;

  // Ждём загрузки расширений перед запросом данных,
  // чтобы fieldsList содержал все поля включая поля из расширений
  const { data } = useReadQuery(
    {
      ...params,
    },
    { skip: isCreateForm || !extensionsLoaded },
  ) as TypedUseQueryHookResult<ReadResult<RecordType>, ReadParams, BaseQueryFn>;

  const { data: dataDefault } = useReadDefaultValuesQuery(
    {
      ...params,
      fields: fieldsList,
    } as ReadParams,
    { skip: !isCreateForm || !extensionsLoaded },
  ) as TypedUseQueryHookResult<
    ReadDefaultValuesResult<RecordType>,
    ReadDefaultValuesParams,
    BaseQueryFn
  >;

  const form = useForm<FaraRecord>({
    mode: 'uncontrolled',
    // initialValues: data || dataDefault,
    enhanceGetInputProps: payload => {
      // пока не инициализирована форма, все поля не доступны
      if (!payload.form.initialized || !Object.keys(fieldsServer).length) {
        return { disabled: true };
      }

      return {};
    },
    // onValuesChange: (values) => {
    //   // ✅ This will be called on every form values change
    //   console.log(values);
    // }
    // transformValues: values => ({
    //   fullName: `${values.firstName} ${values.lastName}`,
    //   age: Number(values.age) || 0,
    // }),
  });

  // Onchange хук - обрабатывает изменения полей с @onchange декоратором
  const { handleFieldChange, onchangeFields } = useOnchange(
    model,
    form,
    setFieldsServer,
  );

  // Panel state (активности / сообщения / вложения)
  const [activePanel, setActivePanel] = useState<PanelType>(null);
  const showPanels = !isCreateForm && id && !modalClose && !parentForm;

  const handleTogglePanel = useCallback((panel: PanelType) => {
    setActivePanel(prev => (prev === panel ? null : panel));
  }, []);

  const handleClosePanel = useCallback(() => {
    setActivePanel(null);
  }, []);

  // console.log(form.getValues(), 'form.getValues()');
  useEffect(() => {
    // Even if data changes, form will be initialized only once
    let formData;
    if (data) {
      formData = data;
    } else if (dataDefault) {
      formData = dataDefault;
    }
    if (formData) {
      setFieldsServer(formData.fields);
      form.reset();
      form.initialize(formData.data);
      form.setValues(formData.data);
      form.resetDirty(formData.data);

      // Устанавливаем валидацию для обязательных полей
      const validation = buildValidation(formData.fields);
      if (Object.keys(validation).length > 0) {
        // @ts-ignore - setFieldValidation не типизирован в Mantine
        for (const [fieldName, validateFn] of Object.entries(validation)) {
          form.setFieldError(fieldName, null); // Очищаем ошибки
        }
      }

      const components = getComponentsFromChildren(
        children,
        formData.fields,
        model,
      );
      setChildrenNew(components);
    }
  }, [data, dataDefault]);

  // Мемоизируем value контекста чтобы избежать лишних ре-рендеров
  // children (M2M, O2M таблицы) при изменении простых полей (name, login и т.д.)
  const formFieldsContextValue = useMemo(
    () => ({
      model,
      fields: fieldsServer,
      setFields: setFieldsServer,
      handleFieldChange,
      onchangeFields,
    }),
    [model, fieldsServer, setFieldsServer, handleFieldChange, onchangeFields],
  );

  // Mobile detection для панели: Drawer вместо inline
  const isMobile = useMediaQuery('(max-width: 575px)');

  return (
    <FormFieldsContext.Provider value={formFieldsContextValue}>
      <FormSettingsProvider
        labelPosition={labelPosition}
        labelWidth={labelWidth}>
        <FormProvider form={form}>
          <ExtensionsContext.Provider value={model}>
            <Box
              style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
              {/* Main form area */}
              <Box style={{ flex: 1, minWidth: 0, overflow: 'auto' }}>
                <Toolbar
                  model={model}
                  id={id}
                  isCreateForm={isCreateForm}
                  fieldsClient={fieldsClient}
                  relatedFieldO2M={relatedFieldO2M}
                  parentFieldName={parentFieldName}
                  parentForm={parentForm}
                  parentId={parentId}
                  modalClose={modalClose}
                  actions={actions}
                  activePanel={activePanel}
                  onTogglePanel={showPanels ? handleTogglePanel : undefined}
                />
                {!!Object.keys(fieldsServer).length && !!childrenNew.length && (
                  <form>{childrenNew}</form>
                )}
              </Box>

              {/* Side panel — mobile: bottom Drawer, desktop: inline resizable */}
              {showPanels && activePanel && (
                isMobile ? (
                  <Drawer
                    opened={!!activePanel}
                    onClose={handleClosePanel}
                    position="bottom"
                    size="85%"
                    withOverlay
                    overlayProps={{ backgroundOpacity: 0.35 }}
                    styles={{
                      content: { borderRadius: '16px 16px 0 0' },
                      body: { padding: 0, height: '100%', display: 'flex', flexDirection: 'column' },
                    }}
                  >
                    <FormPanelSide
                      resModel={model}
                      resId={Number(id)}
                      activePanel={activePanel}
                      onClose={handleClosePanel}
                    />
                  </Drawer>
                ) : (
                  <FormPanelSide
                    resModel={model}
                    resId={Number(id)}
                    activePanel={activePanel}
                    onClose={handleClosePanel}
                  />
                )
              )}
            </Box>
          </ExtensionsContext.Provider>
        </FormProvider>
      </FormSettingsProvider>
    </FormFieldsContext.Provider>
  );
};
