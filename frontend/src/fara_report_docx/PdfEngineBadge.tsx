/**
 * Индикатор движка PDF для администратора (тулбар списка шаблонов):
 * «LibreOffice 7.6» — точная вёрстка Word, «встроенный конвертер» —
 * упрощённая. Подсказка объясняет, как включить LibreOffice; «Проверить
 * снова» ищет его заново без рестарта, если поставили на сервер руками.
 */
import { useEffect } from 'react';
import { ActionIcon, Badge, Group, Tooltip } from '@mantine/core';
import { IconRefresh } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useLazyPdfEngineQuery } from './api';
import { useCanDesignTemplates } from './useCanDesign';

export function PdfEngineBadge() {
  const { t } = useTranslation('reports');
  const canDesign = useCanDesignTemplates();
  const [load, { data, isFetching, error }] = useLazyPdfEngineQuery();

  useEffect(() => {
    if (canDesign) void load({});
  }, [canDesign, load]);

  if (!canDesign) return null;

  const info = data?.data;
  const isLibre = info?.engine === 'libreoffice';
  let label = '…';
  if (error) label = t('pdfEngine.unknown');
  else if (info) {
    label = isLibre
      ? t('pdfEngine.libreoffice', { version: info.version ?? '' })
      : t('pdfEngine.builtin');
  }
  const hint = isLibre
    ? t('pdfEngine.hintLibreoffice', { path: info?.path ?? '' })
    : t('pdfEngine.hintBuiltin');

  return (
    <Group gap={4} wrap="nowrap">
      <Tooltip label={hint} multiline w={340}>
        <Badge
          variant="light"
          color={error ? 'gray' : isLibre ? 'green' : 'yellow'}
          style={{ cursor: 'default' }}>
          {label}
        </Badge>
      </Tooltip>
      <Tooltip label={t('pdfEngine.recheck')}>
        <ActionIcon
          variant="subtle"
          size="sm"
          loading={isFetching}
          aria-label={t('pdfEngine.recheck')}
          onClick={() => void load({ recheck: true })}>
          <IconRefresh size={14} />
        </ActionIcon>
      </Tooltip>
    </Group>
  );
}
