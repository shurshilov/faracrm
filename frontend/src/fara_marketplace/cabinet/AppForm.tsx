import type { FaraRecord } from '@/services/api/crudTypes';
import { useParams } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { Text } from '@mantine/core';
import { IconInfoCircle, IconMessageStar } from '@tabler/icons-react';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import {
  FormRow,
  FormSection,
  FormTab,
  FormTabs,
} from '@/components/Form/Layout';
import { selectCurrentSession } from '@/slices/authSlice';
import { ReviewList } from '../public/ReviewList';
import { GitArchiveForm } from './GitArchiveForm';

/** Суперпользователь или «Администратор настроек»: им доступны флаг
 *  «проверено» (на бэке role_* поля) и архив из GitHub. */
export function useIsMarketAdmin(): boolean {
  const user = useSelector(selectCurrentSession)?.user_id;
  return (
    !!user?.is_admin ||
    (user?.role_ids || []).some(role => role.code === 'system_admin')
  );
}

// Форма приложения поставщика. Файлы — обычные «Вложения» записи (скрепка
// вверху): картинки — скриншоты (первая — обложка), zip — архив модуля;
// админ может вместо загрузки указать папки репозитория GitHub.
// Публикация без zip отклоняется бэкендом.
export function ViewFormMarketplaceApp(props: ViewFormProps) {
  const { t } = useTranslation('marketplace');
  const { id } = useParams<{ id: string }>();
  const isAdmin = useIsMarketAdmin();

  return (
    <Form<FaraRecord> model="marketplace_app" {...props}>
      <FormTabs>
        <FormTab
          name="main"
          label={t('tabs.main')}
          icon={<IconInfoCircle size={16} />}>
          <FormSection title={t('sections.app')}>
            <FormRow cols={2}>
              <Field name="name" label={t('fields.name')} />
              <Field name="category" label={t('fields.category')} />
            </FormRow>
            <FormRow cols={1}>
              <Field name="summary" label={t('fields.summary')} />
            </FormRow>
            <FormRow cols={1}>
              <Field name="description" label={t('fields.description')} />
            </FormRow>
            <FormRow cols={3}>
              <Field name="version" label={t('fields.version')} />
              <Field name="price" label={t('fields.price')} />
              <Field name="published" label={t('fields.published')} />
            </FormRow>
            <FormRow cols={3}>
              <Field name="code" label={t('fields.code')} />
              {isAdmin && (
                <Field name="verified" label={t('fields.verified')} />
              )}
            </FormRow>
          </FormSection>
          <Text size="sm" c="dimmed" mb="md">
            {t('files.hint')}
          </Text>
          {isAdmin && id && <GitArchiveForm appId={Number(id)} />}
        </FormTab>
        <FormTab
          name="reviews"
          label={t('tabs.reviews')}
          icon={<IconMessageStar size={16} />}>
          {id ? (
            <ReviewList appId={Number(id)} />
          ) : (
            <Text size="sm" c="dimmed">
              {t('form.saveFirst')}
            </Text>
          )}
        </FormTab>
      </FormTabs>
    </Form>
  );
}

export default ViewFormMarketplaceApp;
