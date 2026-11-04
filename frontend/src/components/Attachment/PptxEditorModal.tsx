/**
 * Полноэкранный просмотрщик pptx-вложения.
 *
 * Рендерит презентацию через @extend-ai/react-pptx (PptxViewerFrame, ленивый чанк);
 * загрузка файла во вложение — useAttachmentFileEditor, как у docx и xlsx.
 */
import { lazy, Suspense, useRef } from 'react';
import {
  Button,
  Center,
  Group,
  Loader,
  Modal,
  Stack,
  Text,
} from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { downloadAttachment } from '@/utils/attachmentUrls';
import { useAttachmentFileEditor } from './useAttachmentFileEditor';
import type { PptxViewerFrameHandle } from './PptxEditorFrame';

// Задаем ограничение на размер, чтобы WebAssembly-парсер не перегружал вкладку
const MAX_VIEWABLE_SIZE = 10 * 1024 * 1024; // 10 MB

const PptxViewerFrame = lazy(() => import('./PptxEditorFrame'));

interface PptxViewerModalProps {
  attachmentId: number;
  filename?: string | null;
  opened: boolean;
  onClose: () => void;
  onSaved?: (size: number) => void;
}

export function PptxViewerModal({
  attachmentId,
  filename,
  opened,
  onClose,
  onSaved,
}: PptxViewerModalProps) {
  const { t } = useTranslation('common');
  const frameRef = useRef<PptxViewerFrameHandle>(null);

  const { bytes, loadError, handleClose } = useAttachmentFileEditor({
    attachmentId,
    filename,
    opened,
    onClose,
    onSaved,
  });

  const tooLarge = !!bytes && bytes.byteLength > MAX_VIEWABLE_SIZE;

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
      styles={{
        content: { display: 'flex', flexDirection: 'column' },
        body: {
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
        },
      }}>
      <Group
        justify="space-between"
        wrap="nowrap"
        px="md"
        py="xs"
        style={{ borderBottom: '1px solid #e9ecef' }}>
        <Text fw={500} truncate>
          {filename}
        </Text>
        <Group gap="xs" wrap="nowrap">
          <Button size="xs" variant="default" onClick={handleClose}>
            {t('close')}
          </Button>
        </Group>
      </Group>

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
      ) : tooLarge ? (
        <Center style={{ flex: 1 }}>
          <Stack align="center" gap="sm">
            <Text>{t('docxEditor.spreadsheetTooLarge')}</Text>
            <Button
              onClick={() =>
                downloadAttachment(attachmentId, filename ?? undefined)
              }>
              {t('download')}
            </Button>
          </Stack>
        </Center>
      ) : bytes ? (
        <Suspense fallback={fallback}>
          <PptxViewerFrame
            ref={frameRef}
            document={bytes} // Передаем напрямую Uint8Array без .buffer
          />
        </Suspense>
      ) : (
        fallback
      )}
    </Modal>
  );
}

export default PptxViewerModal;
