import {
  IconFile,
  IconFileTypePdf,
  IconFileTypeDoc,
  IconFileTypeDocx,
  IconFileTypeXls,
  IconFileTypeCsv,
  IconFileTypePpt,
  IconFileTypeZip,
  IconFileTypeHtml,
  IconFileTypeTxt,
  IconFileTypeJs,
  IconFileTypeTs,
  IconFileTypeCss,
  IconFileTypeJpg,
  IconFileTypePng,
  IconFileTypeSvg,
  IconVideo,
  IconMusic,
  IconFileCode,
  IconFileText,
  IconFileSpreadsheet,
  IconPresentation,
  IconPhoto,
  IconArchive,
  Icon,
} from '@tabler/icons-react';

export interface FileIconConfig {
  icon: Icon;
  color: string;
}

// Маппинг MIME-типов на иконки и цвета
const mimeTypeMap: Record<string, FileIconConfig> = {
  // PDF
  'application/pdf': { icon: IconFileTypePdf, color: '#e53935' },

  // Word Documents
  'application/msword': { icon: IconFileTypeDoc, color: '#2196f3' },
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': {
    icon: IconFileTypeDocx,
    color: '#2196f3',
  },
  'application/vnd.oasis.opendocument.text': {
    icon: IconFileTypeDoc,
    color: '#2196f3',
  },

  // Excel / Spreadsheets
  'application/vnd.ms-excel': { icon: IconFileTypeXls, color: '#4caf50' },
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': {
    icon: IconFileTypeXls,
    color: '#4caf50',
  },
  'application/vnd.oasis.opendocument.spreadsheet': {
    icon: IconFileSpreadsheet,
    color: '#4caf50',
  },
  'text/csv': { icon: IconFileTypeCsv, color: '#4caf50' },

  // PowerPoint / Presentations
  'application/vnd.ms-powerpoint': { icon: IconFileTypePpt, color: '#ff9800' },
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': {
    icon: IconFileTypePpt,
    color: '#ff9800',
  },
  'application/vnd.oasis.opendocument.presentation': {
    icon: IconPresentation,
    color: '#ff9800',
  },

  // Archives
  'application/zip': { icon: IconFileTypeZip, color: '#795548' },
  'application/x-zip-compressed': { icon: IconFileTypeZip, color: '#795548' },
  'application/x-rar-compressed': { icon: IconArchive, color: '#795548' },
  'application/x-7z-compressed': { icon: IconArchive, color: '#795548' },
  'application/gzip': { icon: IconArchive, color: '#795548' },
  'application/x-tar': { icon: IconArchive, color: '#795548' },

  // Images
  'image/jpeg': { icon: IconFileTypeJpg, color: '#26a69a' },
  'image/jpg': { icon: IconFileTypeJpg, color: '#26a69a' },
  'image/png': { icon: IconFileTypePng, color: '#26a69a' },
  'image/gif': { icon: IconPhoto, color: '#26a69a' },
  'image/webp': { icon: IconPhoto, color: '#26a69a' },
  'image/svg+xml': { icon: IconFileTypeSvg, color: '#ff9800' },
  'image/bmp': { icon: IconPhoto, color: '#26a69a' },
  'image/tiff': { icon: IconPhoto, color: '#26a69a' },

  // Video
  'video/mp4': { icon: IconVideo, color: '#9c27b0' },
  'video/webm': { icon: IconVideo, color: '#9c27b0' },
  'video/ogg': { icon: IconVideo, color: '#9c27b0' },
  'video/quicktime': { icon: IconVideo, color: '#9c27b0' },
  'video/x-msvideo': { icon: IconVideo, color: '#9c27b0' },

  // Audio
  'audio/mpeg': { icon: IconMusic, color: '#e91e63' },
  'audio/mp3': { icon: IconMusic, color: '#e91e63' },
  'audio/wav': { icon: IconMusic, color: '#e91e63' },
  'audio/ogg': { icon: IconMusic, color: '#e91e63' },
  'audio/webm': { icon: IconMusic, color: '#e91e63' },

  // Text
  'text/plain': { icon: IconFileTypeTxt, color: '#607d8b' },
  'text/html': { icon: IconFileTypeHtml, color: '#ff5722' },
  'text/css': { icon: IconFileTypeCss, color: '#2196f3' },
  'text/xml': { icon: IconFileCode, color: '#607d8b' },

  // Code
  'application/javascript': { icon: IconFileTypeJs, color: '#ffc107' },
  'text/javascript': { icon: IconFileTypeJs, color: '#ffc107' },
  'application/typescript': { icon: IconFileTypeTs, color: '#3178c6' },
  'application/json': { icon: IconFileCode, color: '#607d8b' },
  'application/xml': { icon: IconFileCode, color: '#607d8b' },
};

// Маппинг по категориям (fallback)
const categoryMap: Record<string, FileIconConfig> = {
  image: { icon: IconPhoto, color: '#26a69a' },
  video: { icon: IconVideo, color: '#9c27b0' },
  audio: { icon: IconMusic, color: '#e91e63' },
  text: { icon: IconFileText, color: '#607d8b' },
  application: { icon: IconFile, color: '#9e9e9e' },
};

// Дефолтная иконка
const defaultIcon: FileIconConfig = { icon: IconFile, color: '#9e9e9e' };

/**
 * Получить конфигурацию иконки по MIME-типу
 */
export function getFileIconConfig(mimetype?: string | null): FileIconConfig {
  if (!mimetype) return defaultIcon;

  // Точное совпадение
  if (mimeTypeMap[mimetype]) {
    return mimeTypeMap[mimetype];
  }

  // Fallback по категории (image/*, video/*, etc.)
  const category = mimetype.split('/')[0];
  if (categoryMap[category]) {
    return categoryMap[category];
  }

  return defaultIcon;
}

/**
 * Проверить, является ли файл изображением
 */
export function isImageMimetype(mimetype?: string | null): boolean {
  if (!mimetype) return false;
  return mimetype.startsWith('image/');
}

/**
 * Проверить, является ли файл видео
 */
export function isVideoMimetype(mimetype?: string | null): boolean {
  if (!mimetype) return false;
  return mimetype.startsWith('video/');
}

/**
 * Проверить, является ли файл аудио
 */
export function isAudioMimetype(mimetype?: string | null): boolean {
  if (!mimetype) return false;
  return mimetype.startsWith('audio/');
}

/**
 * Форматировать размер файла
 */
export function formatFileSize(bytes?: number | null): string {
  if (!bytes) return '0 B';

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let unitIndex = 0;
  let size = bytes;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }

  return `${size.toFixed(unitIndex > 0 ? 1 : 0)} ${units[unitIndex]}`;
}
