import type { FaraRecord } from '@/services/api/crudTypes';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Text } from '@mantine/core';
import { IconInfoCircle, IconPaperclip } from '@tabler/icons-react';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import {
  FormRow,
  FormSection,
  FormTab,
  FormTabs,
} from '@/components/Form/Layout';
import { AttachmentsPanel } from '@/components/Form/Panels';

// Форма приложения поставщика. Файлы — обычные вложения записи: картинки
// становятся скриншотами (первая — обложкой), zip — архивом модуля.
// Публикация без zip отклоняется бэкендом.
export function ViewFormMarketplaceApp(props: ViewFormProps) {
  const { t } = useTranslation('marketplace');
  const { id } = useParams<{ id: string }>();

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
          </FormSection>
        </FormTab>
        <FormTab
          name="files"
          label={t('tabs.files')}
          icon={<IconPaperclip size={16} />}>
          {id ? (
            <>
              <Text size="sm" c="dimmed" mb="sm">
                {t('files.hint')}
              </Text>
              <AttachmentsPanel resModel="marketplace_app" resId={Number(id)} />
            </>
          ) : (
            <Text size="sm" c="dimmed">
              {t('files.saveFirst')}
            </Text>
          )}
        </FormTab>
      </FormTabs>
    </Form>
  );
}

export default ViewFormMarketplaceApp;
