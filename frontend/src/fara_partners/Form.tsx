import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import type { PartnerRecord as Partner } from '@/types/records';
import {
  FormRow,
  FormCol,
  FormTabs,
  FormTab,
  FormSheet,
} from '@/components/Form/Layout';
import { IconBuilding, IconWorld, IconUsers } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

export function ViewFormPartners(props: ViewFormProps) {
  const { t } = useTranslation('partners');
  return (
    <Form<Partner> model="partners" {...props}>
      {/* Основная информация */}
      <FormSheet avatar={<Field name="image" />}>
        <FormRow cols={2}>
          <FormCol gap="sm">
            <Field name="name" label={t('fields.name')} />
            <Field name="active" label={t('fields.active')} />
          </FormCol>
          <Field
            name="contact_ids"
            widget="contacts"
            label={t('fields.contact_ids')}>
            <Field name="id" />
            <Field name="contact_type_id" />
            <Field name="name" />
            <Field name="is_primary" />
          </Field>
        </FormRow>
      </FormSheet>

      {/* Вкладки */}
      <FormTabs defaultTab="children">
        <FormTab name="common" label="Общие" icon={<IconUsers size={16} />}>
          <FormRow cols={2}>
            <Field name="parent_id" label={t('fields.parent_id')} />
            <Field name="vat" label={t('fields.vat')} />
            <Field name="user_id" label={t('fields.user_id')} />
            <Field name="company_id" label={t('fields.company_id')} />
          </FormRow>
        </FormTab>
        <FormTab
          name="children"
          label="Дочерние партнёры"
          icon={<IconUsers size={16} />}>
          <Field name="child_ids">
            <Field name="id" label={t('fields.id')} />
            <Field name="name" label={t('fields.name')} />
          </Field>
        </FormTab>

        <FormTab name="notes" label="Заметки" icon={<IconBuilding size={16} />}>
          <Field name="notes" label="Заметки" />
        </FormTab>

        {/* Настройки */}
        <FormTab
          name="serrings"
          label="Настройки"
          icon={<IconWorld size={18} />}>
          <FormRow cols={2}>
            <Field name="tz" label="Часовой пояс" />
            <Field name="lang" label="Язык" />
          </FormRow>
        </FormTab>
      </FormTabs>
    </Form>
  );
}
