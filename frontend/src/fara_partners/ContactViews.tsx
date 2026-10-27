import { Form } from '@/components/Form/Form';
import { List } from '@/components/List/List';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import type { ContactRecord } from '@/types/records';
import { FormRow } from '@/components/Form/Layout';
import { Badge, UnstyledButton } from '@mantine/core';
import {
  IconPhone,
  IconMail,
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconBrandInstagram,
  IconWorld,
  IconMessageCircle,
  IconShoppingBag,
  IconSend,
  IconAddressBook,
} from '@tabler/icons-react';
import {
  useContactTypes,
  getContactTypeConfig,
} from '@/components/ContactsWidget';
import { useContactAction } from '@/components/ContactsWidget/useContactAction';

// Маппинг icon name → React component
const ICON_MAP: Record<string, React.ElementType> = {
  IconPhone,
  IconMail,
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconBrandInstagram,
  IconWorld,
  IconMessageCircle,
  IconShoppingBag,
  IconSend,
  phone: IconPhone,
  mail: IconMail,
  send: IconSend,
  'shopping-bag': IconShoppingBag,
  'message-circle': IconMessageCircle,
  camera: IconBrandInstagram,
};

function getIcon(iconName: string): React.ElementType {
  return ICON_MAP[iconName] || IconAddressBook;
}

// ============ LIST ============
// value — РЕАЛЬНОЕ значение (телефон/email/username/extension);
// name — человекочитаемое ОПИСАНИЕ («Александр рабочий телефон»), опционально.
export function ViewListContacts() {
  const { contactTypes } = useContactTypes();
  const contactAction = useContactAction();

  return (
    <List<ContactRecord> model="contact">
      <Field name="id" label="ID" />
      <Field
        name="contact_type_id"
        label="Тип"
        render={(value, record) => {
          const typeName = value?.name || value;
          const config = getContactTypeConfig(typeName, contactTypes);
          const Icon = getIcon(config?.icon || '');
          const badge = (
            <Badge
              size="sm"
              color={config?.color || 'gray'}
              leftSection={<Icon size={14} />}>
              {config?.label || typeName}
            </Badge>
          );
          // Клик по бейджу — номер в звонилку или чат с собеседником
          // (issue #47); запись открывается по остальной строке.
          const action = contactAction({
            id: Number(record.id),
            value: record.value ?? '',
            contact_type: typeName,
            contact_type_id: value?.id,
          });
          if (!action) return badge;
          return (
            <UnstyledButton
              title={action.label}
              onClick={e => {
                e.stopPropagation();
                action.run();
              }}>
              {badge}
            </UnstyledButton>
          );
        }}
      />
      <Field name="value" label="Значение" />
      <Field
        name="name"
        label="Описание"
        render={value => value || '—'}
      />
      <Field
        name="partner_id"
        label="Партнёр"
        render={value => value?.name || '—'}
      />
      <Field
        name="user_id"
        label="Пользователь"
        render={value => value?.name || '—'}
      />
      <Field
        name="is_primary"
        label="Основной"
        render={value => (value ? '⭐' : '—')}
      />
      <Field name="active" label="Активен" />
    </List>
  );
}

// ============ FORM ============

export function ViewFormContacts(props: ViewFormProps) {
  return (
    <Form<ContactRecord> model="contact" {...props}>
      <FormRow cols={2}>
        <Field name="contact_type_id" label="Тип контакта" />
        <Field name="value" label="Значение" />
      </FormRow>
      <FormRow cols={1}>
        <Field name="name" label="Описание (напр. «Александр рабочий телефон»)" />
      </FormRow>
      <FormRow cols={2}>
        <Field name="partner_id" label="Партнёр" />
        <Field name="user_id" label="Пользователь" />
      </FormRow>
      <FormRow cols={2}>
        <Field name="is_primary" label="Основной" />
        <Field name="active" label="Активен" />
      </FormRow>
    </Form>
  );
}
