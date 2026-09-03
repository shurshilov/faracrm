import { Flex, Group, Text, ThemeIcon } from '@mantine/core';
import { FaraRecord } from '@/services/api/crudTypes';
import { ButtonUpdate } from './ButtonUpdate';
import { ButtonCreate } from './ButtonCreate';
import { useFormContext } from './FormContext';
import { UseFormReturnType } from '@mantine/form';
import { ViewSwitcher, ViewType } from '@/components/ViewSwitcher';
import {
  BackToListButton,
  RecordPager,
  useBackToList,
} from '@/components/RecordNav';
import { useCallback, useMemo, useState, useRef, ReactNode } from 'react';
import { FormPanelsBadges, PanelType } from './Panels';
import { IconCheck } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

export const Toolbar = ({
  model,
  id,
  isCreateForm,
  // fieldsClient,
  parentFieldName,
  parentForm,
  parentId,
  relatedFieldO2M,
  modalClose,
  onCreated,
  actions,
  activePanel,
  onTogglePanel,
}: {
  model: string;
  id?: string;
  isCreateForm: boolean;
  // fieldsClient: Field[];
  parentFieldName?: string;
  parentForm?: UseFormReturnType<FaraRecord>;
  parentId?: number;
  relatedFieldO2M?: string;
  modalClose?: () => void;
  onCreated?: (record: FaraRecord) => void;
  actions?: ReactNode;
  activePanel?: PanelType;
  onTogglePanel?: (panel: PanelType) => void;
}) => {
  const { t } = useTranslation('common');
  const form = useFormContext();
  const backToList = useBackToList(model);
  const [showSaved, setShowSaved] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  // Переключение вида с формы: запоминаем выбранный вид и возвращаемся к
  // нему с восстановлением состояния (фильтры, страница) — так же, как
  // кнопка «К списку».
  const handleViewChange = useCallback(
    (newView: ViewType) => {
      if (newView === 'form') return;
      localStorage.setItem(`viewType_${model}`, newView);
      backToList();
    },
    [model, backToList],
  );

  // Не показываем ViewSwitcher если это модальная форма или вложенная форма
  const showViewSwitcher = !modalClose && !parentForm;

  // Показываем панели (активности, сообщения, вложения) для существующих записей
  const showPanels =
    !isCreateForm && id && !modalClose && !parentForm && onTogglePanel;

  return (
    <Flex
      mih={{ base: 44, sm: 50 }}
      gap="xs"
      justify="space-between"
      align="center"
      direction="row"
      wrap="nowrap"
      px="xs">
      <Group gap="xs">
        {/* Навигация по записям: «К списку» и пейджер по выборке, из
            которой открыта форма (без контекста пейджер не рендерится).
            Только у самостоятельной формы — не в попапе и не во вложенной. */}
        {showViewSwitcher && (
          <>
            <BackToListButton model={model} />
            <RecordPager />
          </>
        )}

        {form.isDirty() ? (
          !!isCreateForm ? (
            <ButtonCreate
              model={model}
              parentFieldName={parentFieldName}
              parentForm={parentForm}
              modalClose={modalClose}
              parentId={parentId}
              relatedFieldO2M={relatedFieldO2M}
              onCreated={onCreated}
            />
          ) : (
            !!id && (
              <ButtonUpdate
                model={model}
                id={id}
                // fields={fieldsClient}
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
