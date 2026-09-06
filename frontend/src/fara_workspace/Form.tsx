import type { FaraRecord } from '@/services/api/crudTypes';
import { useTranslation } from 'react-i18next';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { FormSection, FormRow } from '@/components/Form/Layout';
import { IconBriefcase } from '@tabler/icons-react';

// Форма «Рабочего места». app_ids — приложения (App с ui_menu=true), видимые
// в этом РМ. Пикер «Выбрать» отфильтрован по ui_menu и installed (плитку
// неустановленного приложения выдать нельзя); в таблице/модалке показываем
// ui_menu_name (communication/crm/…) — осмысленный ключ. nested
// <Field name="id"> обязателен, иначе m2m ломается и форма не открывается.
export function ViewFormWorkspace(props: ViewFormProps) {
  const { t } = useTranslation('workspace');

  return (
    <Form<FaraRecord> model="workspace" {...props}>
      <FormSection
        title={t('sections.workspace')}
        icon={<IconBriefcase size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label={t('fields.name')} />
          <Field name="sequence" label={t('fields.sequence')} />
        </FormRow>
        <FormRow cols={2}>
          <Field name="active" label={t('fields.active')} />
        </FormRow>
        <FormRow cols={1}>
          <Field
            name="app_ids"
            label={t('fields.app_ids')}
            showSelect
            displayField="ui_menu_name"
            filter={[
              ['ui_menu', '=', true],
              ['installed', '=', true],
            ]}>
            <Field name="id" label={t('fields.id')} />
            <Field name="ui_menu_name" label={t('fields.app')} />
          </Field>
        </FormRow>
      </FormSection>
    </Form>
  );
}

export default ViewFormWorkspace;
