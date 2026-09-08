import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { SchemaUser } from '@/services/api/users';
import {
  FormRow,
  FormCol,
  FormTabs,
  FormTab,
  FormSheet,
} from '@/components/Form/Layout';
import {
  IconShield,
  IconLanguage,
  IconLock,
  IconCopy,
  IconSettings,
  IconUsers,
} from '@tabler/icons-react';
import { FormActions, FormAction } from '@/components/Form/FormActions';
import { ChangePasswordModal } from './ChangePasswordModal';
import { CopyUserModal } from './CopyUserModal';
import { Triplet } from '@/services/api/crudTypes';
import { useFormContext } from '@/components/Form/FormContext';

// Функция для вычисления фильтра lang_id по lang_ids
const getLangFilter = (values: Record<string, any>): Triplet[] => {
  const langIdsData = values?.lang_ids;
  const langIds = langIdsData?.data || langIdsData;
  if (Array.isArray(langIds) && langIds.length > 0) {
    const ids = langIds.map((l: { id: number }) => l.id);
    return [['id', 'in', ids]];
  }
  return [];
};

// Компонент для действий с доступом к данным формы
function UserFormActions({
  onChangePassword,
  onCopyUser,
}: {
  userId: number;
  onChangePassword: () => void;
  onCopyUser: (userData: {
    name: string;
    login: string;
    is_admin: boolean;
  }) => void;
}) {
  const { t } = useTranslation('users');
  const form = useFormContext();

  const actions: FormAction[] = [
    {
      key: 'changePassword',
      label: t('actions.changePassword', 'Сменить пароль'),
      icon: <IconLock size={14} />,
      onClick: onChangePassword,
    },
    {
      key: 'copyUser',
      label: t('actions.copyUser', 'Копировать'),
      icon: <IconCopy size={14} />,
      onClick: () => {
        const values = form.getValues();
        onCopyUser({
          name: values.name || '',
          login: values.login || '',
          is_admin: values.is_admin || false,
        });
      },
    },
  ];

  return <FormActions actions={actions} />;
}

export default function ViewFormUsers(props: ViewFormProps) {
  const { t } = useTranslation('users');
  const { id } = useParams<{ id: string }>();
  const [changePasswordOpen, setChangePasswordOpen] = useState(false);
  const [copyUserOpen, setCopyUserOpen] = useState(false);
  const [userData, setUserData] = useState<{
    name: string;
    login: string;
    is_admin: boolean;
  }>({
    name: '',
    login: '',
    is_admin: false,
  });

  const userId = id ? parseInt(id, 10) : 0;

  const handleCopyUser = (data: {
    name: string;
    login: string;
    is_admin: boolean;
  }) => {
    setUserData(data);
    setCopyUserOpen(true);
  };

  return (
    <>
      <Form<SchemaUser>
        model="users"
        labelWidth={160}
        {...props}
        actions={
          <UserFormActions
            userId={userId}
            onChangePassword={() => setChangePasswordOpen(true)}
            onCopyUser={handleCopyUser}
          />
        }>
        {/* Основной блок с аватаром и ключевой информацией */}
        <FormSheet avatar={<Field name="image" />}>
          <FormRow cols={2}>
            <Field name="name" label={t('fields.name')} />
            <Field
              name="lang_id"
              label={t('fields.lang')}
              filter={getLangFilter}
            />
          </FormRow>
          <FormRow cols={2}>
            <FormCol gap="sm">
              <Field name="login" label={t('fields.login')} />
              <Field
                name="is_admin"
                label={t('fields.is_admin', 'Суперпользователь')}
              />
              {/* Маркетплейс: отметка продавца (ставит system_admin) */}
              <Field
                name="verified"
                label={t('marketplace:fields.vendor_verified')}
              />
            </FormCol>
            <Field
              name="contact_ids"
              widget="contacts"
              label={t('fields.contact_ids', 'Контакты')}>
              <Field name="contact_type_id" />
              <Field name="name" />
              <Field name="is_primary" />
            </Field>
          </FormRow>
        </FormSheet>

        {/* Вкладки с дополнительной информацией */}
        <FormTabs defaultTab="roles">
          <FormTab
            name="roles"
            label={t('tabs.roles')}
            icon={<IconShield size={16} />}>
            <Field name="role_ids" showSelect label="">
              <Field name="id" label={t('fields.id')} />
              <Field name="name" label={t('fields.name')} />
              <Field name="user_ids" label={t('role_ids.user_ids')} />
            </Field>
          </FormTab>

          {/* Команды пользователя (team_ids). Обратная сторона team_crm.user_ids
              — источник {{team_ids}} для доступа к внешним чатам по командам. */}
          <FormTab
            name="teams"
            label={t('tabs.teams', 'Команды')}
            icon={<IconUsers size={16} />}>
            <Field name="team_ids" showSelect label="">
              <Field name="id" label={t('fields.id')} />
              <Field name="name" label={t('fields.name')} />
            </Field>
          </FormTab>

          <FormTab
            name="languages"
            label={t('tabs.languages', 'Доступные языки')}
            icon={<IconLanguage size={16} />}>
            <Field name="lang_ids">
              <Field name="id" label={t('fields.id')} />
              <Field name="code" label={t('lang_ids.code')} />
              <Field name="name" label={t('fields.name')} />
              <Field name="flag" label={t('lang_ids.flag')} />
              <Field name="active" label={t('lang_ids.active')} />
            </Field>
          </FormTab>

          <FormTab
            name="preferences"
            label={t('tabs.preferences', 'Настройки')}
            icon={<IconSettings size={16} />}>
            <FormRow cols={2}>
              <Field
                name="home_page"
                label={t('fields.home_page', 'Домашняя страница')}
              />
              <Field
                name="layout_theme"
                label={t('fields.layout_theme', 'Тема интерфейса')}
              />
            </FormRow>
            {/* «Рабочее место» — какие приложения видит пользователь в
                лаунчере (Many2one → workspace). Админу не назначается. */}
            <FormRow cols={2}>
              <Field
                name="workspace_id"
                label={t('workspace:fields.workspace_id', 'Рабочее место')}
              />
            </FormRow>
          </FormTab>
        </FormTabs>
      </Form>

      {/* Modal for changing password */}
      <ChangePasswordModal
        opened={changePasswordOpen}
        onClose={() => setChangePasswordOpen(false)}
        userId={userId}
      />

      {/* Modal for copying user */}
      <CopyUserModal
        opened={copyUserOpen}
        onClose={() => setCopyUserOpen(false)}
        userId={userId}
        userName={userData.name}
        userLogin={userData.login}
        isAdmin={userData.is_admin}
      />
    </>
  );
}
