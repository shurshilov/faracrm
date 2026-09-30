/**
 * Расширения ядра от модуля отчётов: источник печати для кнопки «Печать» в
 * тулбаре форм всех моделей. Файл extensions.ts в корне модуля подхватывается
 * глобом (см. shared/extensions/useModelExtensions), ядро на модуль не
 * ссылается.
 */
import { registerPrintProvider } from '@/shared/extensions/print';
import { ReportPrintProvider } from './PrintProvider';

registerPrintProvider('report_docx', ReportPrintProvider);
