import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';

import {
  FormRow,
  FormTabs,
  FormTab,
  FormSheet,
} from '@/components/Form/Layout';
import { IconBell, IconAlignBoxLeftTop } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { ActivityRecord, ActivityTypeRecord } from './List';

// ==================== Activity Form ====================

export function ViewFormActivity(props: ViewFormProps) {
  const { t } = useTranslation('activity');
  return (
    <Form<ActivityRecord> model="activity" {...props}>
      <FormSheet>
        <FormRow cols={2}>
          <Field name="summary" label={t('fields.summary')} />
          <Field name="activity_type_id" label={t('fields.activity_type_id')} />
        </FormRow>
        <FormRow cols={2}>
          <Field name="res_model" label={t('fields.res_model')} />
          <Field name="res_id" label={t('fields.res_id')} />
        </FormRow>
        <FormRow cols={3}>
          <Field name="user_id" label={t('fields.user_id')} />
          <Field name="date_deadline" label={t('fields.date_deadline')} />
          <Field name="state" label={t('fields.state')} />
        </FormRow>
        <FormRow cols={3}>
          <Field name="done" label={t('fields.done')} />
          <Field name="create_user_id" label={t('fields.create_user_id')} />
          <Field name="active" label={t('fields.active')} />
        </FormRow>
      </FormSheet>

      <FormTabs defaultTab="note">
        <FormTab
          name="note"
          label={t('sections.note')}
          icon={<IconAlignBoxLeftTop size={16} />}>
          <Field name="note" label={t('fields.note')} />
        </FormTab>
      </FormTabs>
    </Form>
  );
}

// ==================== Activity Type Form ====================

export function ViewFormActivityType(props: ViewFormProps) {
  const { t } = useTranslation('activity');
  return (
    <Form<ActivityTypeRecord> model="activity_type" {...props}>
      <FormSheet>
        <FormRow cols={2}>
          <Field name="name" label={t('fields.name')} />
          <Field name="icon" label={t('fields.icon')} />
        </FormRow>
        <FormRow cols={3}>
          <Field name="color" label={t('fields.color')} />
          <Field name="default_days" label={t('fields.default_days')} />
          <Field name="sequence" label={t('fields.sequence')} />
        </FormRow>
        <Field name="active" label={t('fields.active')} />
      </FormSheet>
    </Form>
  );
}
