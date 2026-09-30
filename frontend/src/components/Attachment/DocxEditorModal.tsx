/**
 * Полноэкранный редактор docx-вложения.
 *
 * Открывает файл через cookie-роут /attachments/{id}/content, правит во
 * встроенном редакторе (DocxEditorFrame, ленивый чанк) и сохраняет обратно
 * обычным PUT /auto/attachments/{id} с base64-контентом — тот же путь, что
 * у замены файла в форме вложения (Attachment.update пишет байты в хранилище).
 *
 * Использование:
 *   <DocxEditorModal attachmentId={id} filename={name} opened onClose={...} />
 */
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import {
  Button,
  Center,
  Group,
  Loader,
  Modal,
  Stack,
  Text,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useTranslation } from 'react-i18next';
import { useUpdateMutation } from '@/services/api/crudApi';
import { attachmentContentUrl } from '@/utils/attachmentUrls';
import { arrayBufferToBase64 } from '@/utils/base64';
import type { DocxEditorFrameHandle } from './DocxEditorFrame';

const DocxEditorFrame = lazy(() =>
  import('./DocxEditorFrame').then(m => ({ default: m.DocxEditorFrame })),
);

interface DocxEditorModalProps {
  attachmentId: number;
  filename?: string | null;
  opened: boolean;
  onClose: () => void;
  /** После успешного сохранения — новый размер файла в байтах. */
  onSaved?: (size: number) => void;
}

export function DocxEditorModal({
  attachmentId,
  filename,
  opened,
  onClose,
  onSaved,
}: DocxEditorModalProps) {
  const { t } = useTranslation('common');
  const frameRef = useRef<DocxEditorFrameHandle>(null);
  const [bytes, setBytes] = useState<Uint8Array | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [update] = useUpdateMutation();

  // Загрузка файла при открытии; при закрытии — сброс, чтобы следующее
  // открытие показало актуальные байты, а не старую копию.
  useEffect(() => {
    if (!opened) {
      setBytes(null);
      setLoadError(null);
      setDirty(false);
      return;
    }
    let cancelled = false;
    fetch(attachmentContentUrl(attachmentId), { credentials: 'include' })
      .then(response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.arrayBuffer();
      })
      .then(buffer => {
        if (!cancelled) setBytes(new Uint8Array(buffer));
      })
      .catch(error => {
        if (!cancelled) setLoadError(String(error));
      });
    return () => {
      cancelled = true;
    };
  }, [opened, attachmentId]);

  const handleSave = useCallback(async () => {
    const buffer = await frameRef.current?.save();
    if (!buffer) return;
    setSaving(true);
    try {
      const content = await arrayBufferToBase64(buffer);
      await update({
        model: 'attachments',
        id: attachmentId,
        values: { content, size: buffer.byteLength },
      }).unwrap();
      setDirty(false);
      notifications.show({ message: t('docxEditor.saved'), color: 'green' });
      onSaved?.(buffer.byteLength);
    } catch (error) {
      notifications.show({
        title: t('docxEditor.saveFailed'),
        message: String(error),
        color: 'red',
      });
    } finally {
      setSaving(false);
    }
  }, [attachmentId, onSaved, t, update]);

  const handleClose = useCallback(() => {
    if (dirty && !window.confirm(t('docxEditor.unsavedClose'))) return;
    onClose();
  }, [dirty, onClose, t]);

  const actions = (
    <Group gap="xs" wrap="nowrap">
      <Button size="xs" onClick={handleSave} loading={saving} disabled={!bytes}>
        {t('save')}
      </Button>
      <Button size="xs" variant="default" onClick={handleClose}>
        {t('close')}
      </Button>
    </Group>
  );

  const fallback = (
    <Center style={{ flex: 1 }}>
      <Loader />
    </Center>
  );

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      fullScreen
      padding={0}
      withCloseButton={false}
      closeOnEscape={!dirty}
      styles={{
        content: { display: 'flex', flexDirection: 'column' },
        body: {
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
        },
      }}>
      {loadError ? (
        <Center style={{ flex: 1 }}>
          <Stack align="center" gap="sm">
            <Text c="red">
              {t('docxEditor.loadFailed')}: {loadError}
            </Text>
            <Button variant="default" onClick={onClose}>
              {t('close')}
            </Button>
          </Stack>
        </Center>
      ) : bytes ? (
        <Suspense fallback={fallback}>
          <DocxEditorFrame
            ref={frameRef}
            document={bytes}
            title={filename || undefined}
            onSave={handleSave}
            onChange={() => setDirty(true)}
            titleBarRight={actions}
          />
        </Suspense>
      ) : (
        fallback
      )}
    </Modal>
  );
}
