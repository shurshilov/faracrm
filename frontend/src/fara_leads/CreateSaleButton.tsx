/**
 * Кнопка «Создать продажу» в тулбаре формы лида — ручной путь той же
 * механики, что автосоздание по стадии-триггеру (POST /leads/{id}/create_sale).
 * Нужна для повторных заказов: у одного лида (клиента) много продаж.
 *
 * Тулбар формы не рендерит actions в режиме создания, поэтому id из маршрута
 * здесь всегда есть. После создания переходим в новую продажу.
 */

import { Button } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconShoppingCartPlus } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { useCreateSaleFromLeadMutation } from './leadsApi';

export function CreateSaleButton() {
  const { t } = useTranslation('leads');
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [createSale, { isLoading }] = useCreateSaleFromLeadMutation();

  const handleClick = async () => {
    try {
      const { sale_id } = await createSale(Number(id)).unwrap();
      navigate(`/sales/${sale_id}`);
    } catch {
      notifications.show({
        color: 'red',
        message: t('sale_link.create_failed'),
      });
    }
  };

  return (
    <Button
      variant="light"
      leftSection={<IconShoppingCartPlus size={16} />}
      onClick={handleClick}
      loading={isLoading}>
      {t('sale_link.create_sale')}
    </Button>
  );
}
