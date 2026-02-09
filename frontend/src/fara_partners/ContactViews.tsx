import { Form } from '@/components/Form/Form';
import { List } from '@/components/List/List';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { FormRow } from '@/components/Form/Layout';
import { Badge } from '@mantine/core';
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
export function ViewListContacts() {
  const { contactTypes } = useContactTypes();

  return (
    <List<ContactRecord> model="contact">
      <Field name="id" label="ID" />
      <Field
        name="contact_type_id"
        label="Тип"
        render={value => {
          const typeName = value?.name || value;
          const config = getContactTypeConfig(typeName, contactTypes);
          const Icon = getIcon(config?.icon || '');
          return (
            <Badge
              size="sm"
              color={config?.color || 'gray'}
              leftSection={<Icon size={14} />}>
              {config?.label || typeName}
            </Badge>
          );
        }}
      />
      <Field name="name" label="Значение" />
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
        <Field name="name" label="Значение" />
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
