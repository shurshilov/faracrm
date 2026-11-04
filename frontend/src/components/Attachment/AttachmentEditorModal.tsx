/**
 * Встроенный редактор вложения по типу файла: xlsx — SpreadsheetEditorModal,
 * docx — DocxEditorModal. Есть ли редактор — canEditAttachment (viewKind).
 */
import { lazy, Suspense } from 'react';
import { DocxEditorModal } from './DocxEditorModal';
import { SpreadsheetEditorModal } from './SpreadsheetEditorModal';
import { isPptxMimetype, isXlsxMimetype } from './fileIcons';

interface AttachmentEditorModalProps {
  attachmentId: number;
  filename?: string | null;
  mimetype?: string | null;
  opened: boolean;
  onClose: () => void;
}

// Ленивая загрузка компонента презентации
const PptxViewerModal = lazy(() => import('./PptxEditorModal'));

export function AttachmentEditorModal({
  mimetype,
  ...props
}: AttachmentEditorModalProps) {
  if (isXlsxMimetype(mimetype, props.filename)) {
    return <SpreadsheetEditorModal {...props} />;
  }

  if (isPptxMimetype(mimetype, props.filename)) {
    return (
      <Suspense fallback={<div>Загрузка просмотрщика...</div>}>
        <PptxViewerModal {...props} />
      </Suspense>
    );
  }

  return <DocxEditorModal {...props} />;
}
