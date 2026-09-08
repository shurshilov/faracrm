import { useState } from 'react';
import { Button, Group, Paper, Text, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconBrandGithub } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useCreateMutation, useSearchQuery } from '@/services/api/crudApi';
import { useFormContext } from '@/components/Form/FormContext';

/**
 * Архив модуля из GitHub (админ): вложение в git-хранилище вместо zip.
 * storage_file_id = «ref:модуль1,модуль2» — GitStorageStrategy сама находит
 * папки модулей в репозитории по имени («модуль» с app.py и fara_<модуль>),
 * путь от корня указывать не нужно. Появляется в списке файлов приложения
 * как обычный zip.
 */
export function GitArchiveForm({ appId }: { appId: number }) {
  const { t } = useTranslation('marketplace');
  const form = useFormContext();
  const code: string = form.getValues()?.code || '';

  const { data: storages } = useSearchQuery({
    model: 'attachments_storage',
    fields: ['id', 'git_repo_url', 'git_ref'],
    filter: [['type', '=', 'git']],
    limit: 1,
  });
  const storage = storages?.data?.[0] as
    | { id: number; git_repo_url: string; git_ref: string | null }
    | undefined;

  const [ref, setRef] = useState('');
  // По умолчанию — код модуля из формы (null, пока админ не правил поле).
  const [modules, setModules] = useState<string | null>(null);
  const moduleNames = (modules ?? code).trim();
  const [create, { isLoading }] = useCreateMutation();

  if (!storage) {
    return (
      <Text size="sm" c="dimmed">
        {t('git.noStorage')}
      </Text>
    );
  }

  const effectiveRef = ref.trim() || storage.git_ref || 'master';

  const handleAdd = async () => {
    await create({
      model: 'attachments',
      values: {
        name: `${code || appId}.zip`,
        mimetype: 'application/zip',
        res_model: 'marketplace_app',
        res_id: appId,
        storage_id: storage.id,
        storage_file_id: `${ref.trim()}:${moduleNames}`,
        storage_file_url: `${storage.git_repo_url}/tree/${effectiveRef}`,
        folder: false,
        public: false,
        show_preview: false,
      },
    }).unwrap();
    notifications.show({ message: t('git.added') });
  };

  return (
    <Paper withBorder p="sm" radius="md" mb="md">
      <Group gap="xs" mb="xs">
        <IconBrandGithub size={16} />
        <Text size="sm" fw={500}>
          {t('git.title')}
        </Text>
        <Text size="xs" c="dimmed">
          {storage.git_repo_url}
        </Text>
      </Group>
      <Group align="flex-end" gap="sm">
        <TextInput
          label={t('git.ref')}
          placeholder={storage.git_ref || 'master'}
          value={ref}
          onChange={e => setRef(e.currentTarget.value)}
          w={160}
        />
        <TextInput
          label={t('git.modules')}
          description={t('git.modulesHint')}
          placeholder="leads"
          value={modules ?? code}
          onChange={e => setModules(e.currentTarget.value)}
          style={{ flex: 1, minWidth: 260 }}
        />
        <Button
          onClick={handleAdd}
          loading={isLoading}
          disabled={!moduleNames}
          variant="light">
          {t('git.add')}
        </Button>
      </Group>
    </Paper>
  );
}
