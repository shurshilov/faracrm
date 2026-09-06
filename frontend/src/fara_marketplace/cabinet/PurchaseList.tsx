import type { FaraRecord } from '@/services/api/crudTypes';
import { Anchor, Button } from '@mantine/core';
import { IconDownload } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { List } from '@/components/List/List';
import { Field } from '@/components/List/Field';
import { DateTimeCell, RelationCell } from '@/components/ListCells';
import { ViewListProps } from '@/route/type';
import { marketDownloadUrl } from '../api';

// «Мои покупки»: оплаченные — со ссылкой на архив; ожидающие оплаты ведут
// на страницу приложения, где кнопка «Купить» вернёт ту же ссылку на оплату.
export function ViewListMarketplacePurchase(props: ViewListProps) {
  const { t } = useTranslation('marketplace');

  return (
    <List<FaraRecord>
      model="marketplace_purchase"
      sort="id"
      order="desc"
      {...props}>
      <Field name="id" label={t('fields.id')} />
      <Field
        name="app_id"
        label={t('fields.app')}
        render={value => <RelationCell value={value} variant="text" />}
      />
      <Field name="amount" label={t('fields.amount')} />
      <Field name="state" label={t('fields.state')} />
      <Field
        name="create_datetime"
        label={t('fields.date')}
        render={value => <DateTimeCell value={value} format="compact" />}
      />
      <Field
        name="payment_id"
        label={t('fields.action')}
        render={(_value, record) =>
          record.state === 'paid' ? (
            <Button
              component="a"
              href={marketDownloadUrl(record.app_id?.id)}
              size="compact-xs"
              variant="light"
              leftSection={<IconDownload size={14} />}
              onClick={e => e.stopPropagation()}>
              {t('purchases.download')}
            </Button>
          ) : (
            <Anchor
              component={Link}
              to={`/market/${record.app_id?.id}`}
              size="sm"
              onClick={e => e.stopPropagation()}>
              {t('purchases.pay')}
            </Anchor>
          )
        }
      />
    </List>
  );
}

export default ViewListMarketplacePurchase;
