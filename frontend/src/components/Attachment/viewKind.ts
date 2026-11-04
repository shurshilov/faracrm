/**
 * Как показать вложение без скачивания (issue #62; набор форматов — по
 * модулям предпросмотра MuK для Odoo): в окне просмотра, во вкладке
 * браузера или во встроенном редакторе. Одно место, где решается по типу
 * файла.
 */
import {
  isAudioMimetype,
  isDocxMimetype,
  isImageMimetype,
  isPptxMimetype,
  isVideoMimetype,
  isXlsxMimetype,
} from './fileIcons';

export type ViewKind =
  // Окно просмотра (AttachmentViewerModal)
  | 'image'
  | 'video'
  | 'audio'
  | 'markdown'
  | 'email'
  | 'text'
  // Вкладка браузера: PDF как есть, документы — PDF через LibreOffice
  | 'pdf'
  | 'office'
  // Встроенный редактор: docx, xlsx (AttachmentEditorModal)
  | 'editor';

const WINDOW_VIEW_KINDS = new Set<ViewKind>([
  'image',
  'video',
  'audio',
  'markdown',
  'email',
  'text',
]);

// Как OFFICE_PDF_SUFFIXES на бэке: форматы LibreOffice Writer
const OFFICE_EXTENSIONS = new Set(['doc', 'docm', 'odt', 'ott', 'fodt', 'rtf']);

// Текст и код показываются исходником — HTML и XML тоже: окно рисует
// текст, а не разметку. Превью отдаёт их текстом (PREVIEW_AS_TEXT_TYPES
// на бэке; json — как есть)
const TEXT_MIMETYPES = new Set([
  'application/json',
  'application/xml',
  'application/javascript',
  'application/x-sh',
  'application/x-yaml',
  'application/sql',
]);
const TEXT_EXTENSIONS = new Set([
  'txt',
  'log',
  'csv',
  'tsv',
  'json',
  'xml',
  'yaml',
  'yml',
  'ini',
  'conf',
  'cfg',
  'sql',
  'html',
  'htm',
  'css',
  'js',
  'ts',
  'py',
  'sh',
  'bat',
  'java',
  'c',
  'h',
  'cpp',
  'cs',
  'go',
  'php',
  'rb',
]);

/** Есть ли у файла встроенный редактор (AttachmentEditorModal). */
export function canEditAttachment(
  mimetype?: string | null,
  name?: string | null,
): boolean {
  return (
    isDocxMimetype(mimetype, name) ||
    isXlsxMimetype(mimetype, name) ||
    isPptxMimetype(mimetype, name)
  );
}

function extensionOf(name?: string | null): string {
  const dot = name?.lastIndexOf('.') ?? -1;
  return dot >= 0 ? name!.slice(dot + 1).toLowerCase() : '';
}

export function getViewKind({
  mimetype,
  name,
}: {
  mimetype?: string | null;
  name?: string | null;
}): ViewKind | null {
  const extension = extensionOf(name);
  if (isImageMimetype(mimetype)) return 'image';
  if (isVideoMimetype(mimetype)) return 'video';
  if (isAudioMimetype(mimetype)) return 'audio';
  if (mimetype === 'application/pdf' || extension === 'pdf') return 'pdf';
  if (canEditAttachment(mimetype, name)) return 'editor';
  if (OFFICE_EXTENSIONS.has(extension)) return 'office';
  if (mimetype === 'text/markdown' || extension === 'md') return 'markdown';
  if (mimetype === 'message/rfc822' || extension === 'eml') return 'email';
  if (
    mimetype?.startsWith('text/') ||
    TEXT_MIMETYPES.has(mimetype ?? '') ||
    TEXT_EXTENSIONS.has(extension)
  ) {
    return 'text';
  }
  return null;
}

/**
 * Можно ли открыть текст во вкладке: превью отдаёт его текстом (как
 * preview_type на бэке). Файл без типа (octet-stream) превью скачивает.
 */
export function canOpenTextInTab(mimetype?: string | null): boolean {
  if (!mimetype) return false;
  return (
    mimetype.startsWith('text/') ||
    mimetype.endsWith('+xml') ||
    TEXT_MIMETYPES.has(mimetype)
  );
}

/** Показывается ли этот вид в окне просмотра (а не во вкладке/редакторе). */
export function isWindowViewKind(kind: ViewKind | null): boolean {
  return kind !== null && WINDOW_VIEW_KINDS.has(kind);
}
