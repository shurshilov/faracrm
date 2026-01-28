import { Button } from '@mantine/core';
import { useNavigate } from 'react-router-dom';
import { FormFieldsContext, useFormContext } from './FormContext';
import { useCreateMutation } from '@/services/api/crudApi';
import { UseFormReturnType } from '@mantine/form';
import { FaraRecord, VirtualId } from '@/services/api/crudTypes';
import { useContext } from 'react';
import { prepareValuesToSave } from './utils';

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

export function ButtonCreate({
  model,
  parentFieldName,
  parentForm,
  parentId,
  relatedFieldO2M,
  modalClose,
}: {
  model: string;
  parentFieldName?: string;
  parentForm?: UseFormReturnType<FaraRecord>;
  parentId?: number;
  relatedFieldO2M?: string;
  modalClose?: () => void;
}) {
  const { fields: fieldsServer } = useContext(FormFieldsContext);
  const form = useFormContext();
  const navigate = useNavigate();
  const [create, { isLoading }] = useCreateMutation();
  return (
    <Button
      loading={isLoading}
      variant="filled"
      onClick={async () => {
        // Валидация обязательных полей
        if (!validateRequiredFields(form, fieldsServer)) {
          return; // Прерываем создание если есть ошибки
        }

        // ONE2MANY
        // если создание происходит из O2M и поле не задано, то
        // необходимо добавить ид родителя для свзяи
        if (relatedFieldO2M)
          if (parentId) form.setValues({ [relatedFieldO2M]: { id: parentId } });
          // при создании записи, еще нет ид из бд
          // но при этом необходимо сделать связи в связанных таблицах
          // поэтому используется статическое значение виртуальный ид
          else form.setValues({ [relatedFieldO2M]: { id: VirtualId } });

        const values = form.getValues();
        // добавить текущую форму в родительское поле O2M
        if (parentFieldName && parentForm && modalClose) {
          // если форма является вложенной в другую,
          // например это форма вызванная из m2m или o2m
          // как модальное окно, то не надо делать запрос в базу
          // просто локально необходимо сохранить новые данные в форму
          // для жтого используется тоде имя с префиксом _
          const parentFormName = '_' + parentFieldName;
          // вообще этот компонент не должен делать логику сохранения
          // прошлых значений вместо этого он должен просто передать новое
          // необходимо перенести код позже
          const oldSource = parentForm.getValues()[parentFieldName];
          let old = { created: [], deleted: [] };
          if (parentFormName in parentForm.getValues())
            old = parentForm.getValues()[parentFormName];
          // добавляем новую строку в родительское скрытое поле
          let virtualId = oldSource.total + old.created.length;
          values['_color'] = 'new';
          values['id'] = 'virtual' + virtualId.toString();

          parentForm.setValues({
            [parentFormName]: {
              deleted: old.deleted,
              created: [...old.created, values],
              fieldsServer: fieldsServer,
            },
          });

          modalClose();
        } else {
          // необходимо найти все o2m и m2m и их _
          // найти все created и заменить на values
          // const valuesCreate: Omit<FaraRecord, 'id'> = {};
          // for (let [fieldName, fieldValue] of Object.entries(values)) {
          //   if (fieldName.startsWith('_'))
          //     valuesCreate[fieldName.substring(1)] = fieldValue;
          //   else if (!('_' + fieldName in values)) {
          //     valuesCreate[fieldName] = fieldValue;
          //   }
          // }
          // console.log(valuesCreate, 'valuesCreate');
          const valuesToCreate = structuredClone(form.getValues());
          prepareValuesToSave(fieldsServer, valuesToCreate);
          const { data } = await create({
            model,
            values: valuesToCreate,
          });
          if (data?.id) navigate(`/${model}/${data?.id}`);
          else navigate(`/${model}`);
        }
      }}>
      {parentFieldName && parentForm ? 'Create local' : 'Create'}
    </Button>
  );
}
