import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { SchemaAccessList } from '@/services/api/access_list';
import { SchemaRole } from '@/services/api/roles';
import { SchemaRule } from '@/services/api/rules';
import { SchemaModel, Session } from '@/services/api/sessions';
import { SchemaApp } from '@/services/api/apps';
import {
  FormSection,
  FormRow,
  FormTabs,
  FormTab,
} from '@/components/Form/Layout';
import {
  IconShield,
  IconLock,
  IconUsers,
  IconList,
  IconInfoCircle,
  IconClock,
  IconApps,
} from '@tabler/icons-react';

/**
 * Форма приложений
 */
export function ViewFormApps(props: ViewFormProps) {
  return (
    <Form<SchemaApp> model="apps" {...props}>
      <FormSection title="Приложение" icon={<IconApps size={18} />}>
        <FormRow cols={2}>
          <Field name="code" />
          <Field name="name" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="id" />
          <Field name="active" />
        </FormRow>
      </FormSection>
    </Form>
  );
}

/**
 * Форма списка доступа (ACL)
 */
export function ViewFormAccessList(props: ViewFormProps) {
  return (
    <Form<SchemaAccessList> model="access_list" {...props}>
      {/* Основная информация */}
      <FormSection
        title="Основная информация"
        icon={<IconInfoCircle size={18} />}>
        <FormRow cols={2}>
          <Field name="name" />
          <Field name="active" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="model_id" />
          <Field name="role_id" />
        </FormRow>
        <Field name="id" />
      </FormSection>

      {/* Права доступа */}
      <FormSection title="Права доступа" icon={<IconLock size={18} />}>
        <FormRow cols={4}>
          <Field name="perm_create" />
          <Field name="perm_read" />
          <Field name="perm_update" />
          <Field name="perm_delete" />
        </FormRow>
      </FormSection>
    </Form>
  );
}

/**
 * Форма ролей
 */
export function ViewFormRoles(props: ViewFormProps) {
  return (
    <Form<SchemaRole> model="roles" {...props}>
      {/* Основная информация */}
      <FormSection title="Основная информация" icon={<IconShield size={18} />}>
        <FormRow cols={2}>
          <Field name="name" />
          <Field name="model_id" />
        </FormRow>
        <Field name="id" />
      </FormSection>

      {/* Вкладки с связанными данными */}
      <FormTabs defaultTab="acl">
        <FormTab name="acl" label="Права доступа" icon={<IconLock size={16} />}>
          <Field name="acl_ids">
            <Field name="id" />
            <Field name="name" />
            <Field name="model_id" />
            <Field name="role_id" />
          </Field>
        </FormTab>

        <FormTab name="rules" label="Правила" icon={<IconList size={16} />}>
          <Field name="rule_ids">
            <Field name="id" />
            <Field name="name" />
            <Field name="role_id" />
          </Field>
        </FormTab>

        <FormTab
          name="users"
          label="Пользователи"
          icon={<IconUsers size={16} />}>
          <Field name="user_ids">
            <Field name="id" />
            <Field name="name" />
            <Field name="role_ids" />
          </Field>
        </FormTab>
      </FormTabs>
    </Form>
  );
}

/**
 * Форма правил
 */
export function ViewFormRules(props: ViewFormProps) {
  return (
    <Form<SchemaRule> model="rules" {...props}>
      <FormSection title="Правило" icon={<IconList size={18} />}>
        <FormRow cols={2}>
          <Field name="name" />
          <Field name="role_id" />
        </FormRow>
        <FormSection title="Права доступа" icon={<IconLock size={18} />}>
          <FormRow cols={4}>
            <Field name="perm_create" />
            <Field name="perm_read" />
            <Field name="perm_update" />
            <Field name="perm_delete" />
          </FormRow>
        </FormSection>
        {/* <Field name="id" /> */}
      </FormSection>
    </Form>
  );
}

/**
 * Форма моделей
 */
export function ViewFormModels(props: ViewFormProps) {
  return (
    <Form<SchemaModel> model="models" {...props}>
      <FormSection title="Модель" icon={<IconInfoCircle size={18} />}>
        <FormRow cols={2}>
          <Field name="id" />
          <Field name="name" />
        </FormRow>
      </FormSection>
    </Form>
  );
}

/**
 * Форма сессий
 */
export function ViewFormSessions(props: ViewFormProps) {
  return (
    <Form<Session> model="sessions" {...props}>
      {/* Основная информация */}
      <FormSection title="Информация о сессии" icon={<IconShield size={18} />}>
        <FormRow cols={2}>
          <Field name="user_id" />
          <Field name="active" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="id" />
          <Field name="token" />
        </FormRow>
      </FormSection>

      {/* Время жизни */}
      <FormSection title="Время жизни" icon={<IconClock size={18} />}>
        <FormRow cols={2}>
          <Field name="ttl" />
          <Field name="expired_datetime" />
        </FormRow>
      </FormSection>

      {/* Аудит */}
      <FormSection
        title="Аудит"
        icon={<IconInfoCircle size={18} />}
        collapsible
        defaultOpened={false}>
        <FormRow cols={2}>
          <Field name="create_datetime" />
          <Field name="create_user_id" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="update_datetime" />
          <Field name="update_user_id" />
        </FormRow>
      </FormSection>
    </Form>
  );
}
