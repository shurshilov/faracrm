import { Button, ButtonProps, Modal } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { getModelViews } from '@/route/Routers';
import { Suspense, useMemo, useCallback } from 'react';
import LoadingScreen from '../LoadingScreen/LoadingScreen';
import { useFormContext } from './FormContext';
import { crudApi } from '@/services/api/crudApi';
import { useDispatch } from 'react-redux';

interface ButtonModalCreateProps {
  model: string;
  relatedFieldO2M?: string;
  parentFieldName?: string;
  parentId?: number;
  buttonProps?: ButtonProps & { children?: React.ReactNode };
}

export function ButtonModalCreate({
  model,
  relatedFieldO2M,
  parentFieldName,
  parentId,
  buttonProps,
}: ButtonModalCreateProps) {
  const form = useFormContext();
  const dispatch = useDispatch();
  const [opened, { open, close }] = useDisclosure(false);
  const views = useMemo(() => getModelViews(model), [model]);
  const Form = views?.form;

  // После создания записи - инвалидируем кэш чтобы обновить список O2M
  const handleCreated = useCallback(
    (newId: number) => {
      // Инвалидируем search запросы для этой модели
      dispatch(crudApi.util.invalidateTags([{ type: 'Record', id: 'LIST' }]));
    },
    [dispatch],
  );

  if (!Form) return null;

  const { children: buttonChildren = 'Создать', ...restButtonProps } =
    buttonProps || {};

  return (
    <>
      <Modal
        opened={opened}
        onClose={close}
        title={`Создание: ${model}`}
        centered
        size="lg">
        <Suspense
          fallback={
            <div className="flex flex-auto flex-col h-[100vh]">
              <LoadingScreen />
            </div>
          }>
          <Form
            isCreateForm={true}
            modalClose={close}
            relatedFieldO2M={relatedFieldO2M}
            parentFieldName={parentFieldName}
            parentForm={form}
            parentId={parentId}
            onCreated={handleCreated}
          />
        </Suspense>
      </Modal>
      <Button variant="filled" onClick={open} {...restButtonProps}>
        {buttonChildren}
      </Button>
    </>
  );
}
