import { Flex, Group } from '@mantine/core';
import { useNavigate } from 'react-router-dom';
import { FaraRecord } from '@/services/api/crudTypes';
import { ButtonUpdate } from './ButtonUpdate';
import { ButtonCreate } from './ButtonCreate';
import { Field } from '@/types/fields';
import { useFormContext } from './FormContext';
import { UseFormReturnType } from '@mantine/form';
import { ViewSwitcher, ViewType } from '@/components/ViewSwitcher';
import { useCallback, useMemo, ReactNode } from 'react';

export const Toolbar = <RecordType extends FaraRecord>({
  model,
  id,
  isCreateForm,
  fieldsClient,
  parentFieldName,
  parentForm,
  parentId,
  relatedFieldO2M,
  modalClose,
  actions,
}: {
  model: string;
  id?: string;
  isCreateForm: boolean;
  fieldsClient: Field[];
  parentFieldName?: string;
  parentForm?: UseFormReturnType<FaraRecord>;
  parentId?: number;
  relatedFieldO2M?: string;
  modalClose?: () => void;
  actions?: ReactNode;
}) => {
  const form = useFormContext();
  const navigate = useNavigate();

  // Получаем доступные views из localStorage (сохраняются ModelView)
  const availableViews = useMemo<ViewType[]>(() => {
    const saved = localStorage.getItem(`availableViews_${model}`);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return ['list', 'form'];
      }
    }
    return ['list', 'form'];
  }, [model]);

  const handleViewChange = useCallback((newView: ViewType) => {
    if (newView === 'list' || newView === 'kanban') {
      // Сохраняем выбранный view и переходим к списку
      localStorage.setItem(`viewType_${model}`, newView);
      navigate(`/${model}`);
    }
    // Если form - ничего не делаем, мы уже в форме
  }, [navigate, model]);

  // Не показываем ViewSwitcher если это модальная форма или вложенная форма
  const showViewSwitcher = !modalClose && !parentForm;

  return (
    <>
      <Flex
        mih={50}
        gap="xs"
        justify="space-between"
        align="center"
        direction="row"
        wrap="nowrap"
        px="xs"
      >
        <Group gap="xs">
          {form.isDirty() &&
            (!!isCreateForm ? (
              <ButtonCreate
                model={model}
                parentFieldName={parentFieldName}
                parentForm={parentForm}
                modalClose={modalClose}
                parentId={parentId}
                relatedFieldO2M={relatedFieldO2M}
              />
            ) : (
              !!id && (
                <ButtonUpdate
                  model={model}
                  id={id}
                  fields={fieldsClient}
                  parentId={parentId}
                  relatedFieldO2M={relatedFieldO2M}
                />
              )
            ))}
        </Group>

        <Group gap="xs">
          {/* Actions dropdown - показываем только для существующих записей */}
          {!isCreateForm && id && actions}
          
          {showViewSwitcher && (
            <ViewSwitcher
              value="form"
              onChange={handleViewChange}
              availableViews={availableViews}
            />
          )}
        </Group>
      </Flex>
    </>
  );
};
