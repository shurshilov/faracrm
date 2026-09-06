import type { FaraRecord } from '@/services/api/crudTypes';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { List } from '@/components/List/List';
import { Field } from '@/components/List/Field';
import { ViewListProps } from '@/route/type';
import { selectCurrentSession } from '@/slices/authSlice';

// «Мои приложения» — кабинет поставщика: только свои записи. Чужие
// опубликованные приложения тоже читаемы (правило каталога), но здесь
// они не нужны — за ними на публичную страницу /market.
export function ViewListMarketplaceApp(props: ViewListProps) {
  const { t } = useTranslation('marketplace');
  const userId = useSelector(selectCurrentSession)?.user_id?.id;

  return (
    <List<FaraRecord>
      model="marketplace_app"
      sort="id"
      order="desc"
      {...props}
      filter={[...(props.filter ?? []), ['create_user_id', '=', userId]]}>
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="category" label={t('fields.category')} />
      <Field name="version" label={t('fields.version')} />
      <Field name="price" label={t('fields.price')} />
      <Field name="published" label={t('fields.published')} />
      <Field name="downloads" label={t('fields.downloads')} />
    </List>
  );
}

export default ViewListMarketplaceApp;
