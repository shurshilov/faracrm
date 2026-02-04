import { Flex, Group, Text, ThemeIcon } from '@mantine/core';
import { useNavigate } from 'react-router-dom';
import { FaraRecord } from '@/services/api/crudTypes';
import { ButtonUpdate } from './ButtonUpdate';
import { ButtonCreate } from './ButtonCreate';
import { Field } from '@/types/fields';
import { useFormContext } from './FormContext';
import { UseFormReturnType } from '@mantine/form';
import { ViewSwitcher, ViewType } from '@/components/ViewSwitcher';
import { useCallback, useMemo, useState, useRef, ReactNode } from 'react';
import { FormPanelsBadges, PanelType } from './Panels';
import { IconCheck } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

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
  activePanel,
  onTogglePanel,
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
  activePanel?: PanelType;
  onTogglePanel?: (panel: PanelType) => void;
}) => {
  const { t } = useTranslation('common');
  const form = useFormContext();
  const navigate = useNavigate();
  const [showSaved, setShowSaved] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const handleSaveSuccess = useCallback(() => {
    setShowSaved(true);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setShowSaved(false), 2000);
  }, []);

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

  const handleViewChange = useCallback(
    (newView: ViewType) => {
      if (newView === 'list' || newView === 'kanban') {
        localStorage.setItem(`viewType_${model}`, newView);
        navigate(`/${model}`);
      }
    },
    [navigate, model],
  );

  // Не показываем ViewSwitcher если это модальная форма или вложенная форма
  const showViewSwitcher = !modalClose && !parentForm;

  // Показываем панели (активности, сообщения, вложения) для существующих записей
  const showPanels =
    !isCreateForm && id && !modalClose && !parentForm && onTogglePanel;

  return (
    <Flex
      mih={50}
      gap="xs"
      justify="space-between"
      align="center"
      direction="row"
      wrap="nowrap"
      px="xs">
      <Group gap="xs">
        {form.isDirty() ? (
          !!isCreateForm ? (
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
                onSaveSuccess={handleSaveSuccess}
              />
            )
          )
        ) : (
          showSaved && (
            <Group gap={4}>
              <ThemeIcon size="xs" color="green" variant="light">
                <IconCheck size={12} />
              </ThemeIcon>
              <Text size="sm" c="green">
                {t('saved')}
              </Text>
            </Group>
          )
        )}
      </Group>

      <Group gap="xs">
        {/* Полиморфные панели: иконки-бейджи */}
        {showPanels && (
          <FormPanelsBadges
            resModel={model}
            resId={Number(id)}
            activePanel={activePanel!}
            onToggle={onTogglePanel!}
          />
        )}

        {/* Custom actions from individual forms */}
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
  );
};
