import { useTranslation } from 'react-i18next';
import { Text } from '@mantine/core';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import RelationCell from '@/components/ListCells/RelationCell';
import { ViewFormProps } from '@/route/type';
import { FormSection, FormRow } from '@/components/Form/Layout';
import { IconPhone, IconUser, IconSettings } from '@tabler/icons-react';
import type { RelationRecord } from '@/types/records';
import { SipPasswordField } from '@/fara_sip_phone/SipPasswordField';

// Модель phone_number (номера телефонии: extension / trunk / group / queue),
// наполняется синхронизацией номеров Asterisk. Обычный список + форма (как
// chat_external_account) — раздел «Номера».
interface PhoneNumberRecord {
  id: number;
  name?: string;
  number?: string;
  extension?: string;
  kind?: string;
  external_id?: string;
  connector_id?: RelationRecord | null;
  user_id?: RelationRecord | null;
  lead_generation?: string;
  lead_generation_missed?: string;
  create_partner?: boolean;
  ignore?: boolean;
  active?: boolean;
}

// === List ===
export function ViewListPhoneNumber() {
  const { t } = useTranslation('chat');

  return (
    <List<PhoneNumberRecord> model="phone_number" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field
        name="extension"
        label={t('phoneNumber.fields.extension', 'Extension')}
      />
      <Field name="number" label={t('phoneNumber.fields.number', 'Номер')} />
      <Field
        name="kind"
        label={t('phoneNumber.fields.kind', 'Тип')}
        render={value => value || '—'}
      />
      <Field
        name="connector_id"
        label={t('fields.connector_id')}
        render={value => <RelationCell value={value} model="chat_connector" />}
      />
      <Field
        name="user_id"
        label={t('phoneNumber.fields.user', 'Сотрудник')}
        render={value => <RelationCell value={value} model="users" />}
      />
      <Field name="active" label={t('fields.active')} />
    </List>
  );
}

// === Form ===
export function ViewFormPhoneNumber(props: ViewFormProps) {
  const { t } = useTranslation('chat');

  return (
    <Form<PhoneNumberRecord> model="phone_number" {...props}>
      <FormSection
        title={t('phoneNumber.groups.info', 'Номер')}
        icon={<IconPhone size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label={t('fields.name')} />
          <Field name="kind" label={t('phoneNumber.fields.kind', 'Тип')} />
        </FormRow>
        <FormRow cols={2}>
          <Field
            name="number"
            label={t('phoneNumber.fields.number', 'Номер')}
          />
          <Field
            name="extension"
            label={t('phoneNumber.fields.extension', 'Extension')}
          />
        </FormRow>
        <FormRow cols={2}>
          <Field
            name="external_id"
            label={t('phoneNumber.fields.externalId', 'ID у провайдера')}
          />
          <Field name="active" label={t('fields.active')} />
        </FormRow>
      </FormSection>

      <FormSection
        title={t('phoneNumber.groups.owner', 'Привязка')}
        icon={<IconUser size={18} />}>
        <FormRow cols={2}>
          <Field name="connector_id" label={t('fields.connector_id')} />
          <Field
            name="user_id"
            label={t('phoneNumber.fields.user', 'Сотрудник (оператор)')}
          />
        </FormRow>
        <Field
          name="create_partner"
          label={t(
            'phoneNumber.fields.createPartner',
            'Создавать партнёра по звонкам',
          )}
        />
        <Text size="xs" c="dimmed">
          {t(
            'phoneNumber.hints.createPartner',
            'Для операторских линий (extension + сотрудник) по умолчанию выключено: ' +
              'звонок с/на такой номер — внутренний (сотрудник↔сотрудник), партнёр не создаётся.',
          )}
        </Text>
        <SipPasswordField />
      </FormSection>

      <FormSection
        title={t('phoneNumber.groups.lead', 'Лидогенерация')}
        icon={<IconSettings size={18} />}>
        <FormRow cols={2}>
          <Field
            name="lead_generation"
            label={t('phoneNumber.fields.leadGeneration', 'Лид (отвеченный)')}
          />
          <Field
            name="lead_generation_missed"
            label={t(
              'phoneNumber.fields.leadGenerationMissed',
              'Лид (пропущенный)',
            )}
          />
        </FormRow>
        <Field
          name="ignore"
          label={t('phoneNumber.fields.ignore', 'Игнорировать в истории')}
        />
      </FormSection>
    </Form>
  );
}
