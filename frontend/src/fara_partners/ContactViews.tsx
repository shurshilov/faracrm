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
} from '@tabler/icons-react';

// Конфиг типов контактов для отображения
const CONTACT_TYPE_CONFIG: Record<
  string,
  { label: string; color: string; icon: React.ReactNode }
> = {
  phone: { label: 'Телефон', color: 'green', icon: <IconPhone size={14} /> },
  email: { label: 'Email', color: 'blue', icon: <IconMail size={14} /> },
  telegram: {
    label: 'Telegram',
    color: 'cyan',
    icon: <IconBrandTelegram size={14} />,
  },
  whatsapp: {
    label: 'WhatsApp',
    color: 'teal',
    icon: <IconBrandWhatsapp size={14} />,
  },
  instagram: {
    label: 'Instagram',
    color: 'pink',
    icon: <IconBrandInstagram size={14} />,
  },
  viber: { label: 'Viber', color: 'violet', icon: null },
  website: { label: 'Сайт', color: 'indigo', icon: <IconWorld size={14} /> },
};

// ============ LIST ============
export function ViewListContacts() {
  return (
    <List model="contact">
      <Field name="id" label="ID" />
      <Field
        name="contact_type"
        label="Тип"
        render={value => {
          const config = CONTACT_TYPE_CONFIG[value] || {
            label: value,
            color: 'gray',
          };
          return (
            <Badge size="sm" color={config.color} leftSection={config.icon}>
              {config.label}
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
interface Contact {
  id?: number;
  contact_type: string;
  name: string;
  partner_id?: { id: number; name: string } | null;
  user_id?: { id: number; name: string } | null;
  is_primary?: boolean;
  active?: boolean;
}

export function ViewFormContacts(props: ViewFormProps) {
  return (
    <Form<Contact> model="contact" {...props}>
      <FormRow cols={2}>
        <Field name="contact_type" label="Тип контакта" />
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
