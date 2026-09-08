import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { useFormContext } from '@/components/Form/FormContext';
import { registerExtension } from '@/shared/extensions';
import { Alert, Text } from '@mantine/core';
import { IconBrandGithub } from '@tabler/icons-react';

/**
 * Расширение формы хранилища для GitHub-репозитория.
 * Добавляется в таб "connection" (по аналогии с attachments_yandex).
 */
export function ViewFormStorageGit() {
  const form = useFormContext();

  // Показываем только для типа git
  if (form.values?.type !== 'git') {
    return null;
  }

  return (
    <FormSection
      title="GitHub"
      icon={<IconBrandGithub size={18} />}
      collapsible>
      <Alert icon={<IconBrandGithub size={20} />} color="gray" mb="md">
        <Text size="sm">
          Хранилище только для чтения: вложение в нём — модули репозитория на
          ветке или теге, архив собирает сервер при скачивании (папки модуля
          находятся по имени в любой подпапке: «модуль» с app.py и
          «fara_модуль»). Такое хранилище не бывает активным и в маршруты
          загрузки не попадает. Токен нужен для приватных репозиториев и лимитов
          API (права: только чтение содержимого).
        </Text>
      </Alert>

      <FormRow cols={2}>
        <FieldChar
          name="git_repo_url"
          label="Репозиторий"
          placeholder="https://github.com/owner/repo"
        />
        <FieldChar
          name="git_ref"
          label="Ветка / тег по умолчанию"
          placeholder="master"
        />
      </FormRow>
      <FormRow cols={1}>
        <FieldChar
          name="git_token"
          label="Токен доступа"
          placeholder="github_pat_…"
          description="Fine-grained token с правом Contents: read"
        />
      </FormRow>
    </FormSection>
  );
}

// Регистрируем расширение для модели attachments_storage
registerExtension(
  'attachments_storage',
  ViewFormStorageGit,
  'after:FormTab:connection',
  ['git_repo_url', 'git_ref', 'git_token'],
);

export default ViewFormStorageGit;
