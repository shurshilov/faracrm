/**
 * Кнопка «Печать» тулбара формы (у каждой сохранённой записи).
 *
 * Ядро не знает, что печатать: пункты собирают провайдеры модулей
 * (registerPrintProvider в shared/extensions/print) — например, DOCX-шаблоны
 * из fara_report_docx. Провайдеры рендерятся невидимо всегда (им нужны свои
 * запросы и права), кнопка появляется, когда есть хоть один пункт: один —
 * действие сразу по клику, несколько — меню с группами.
 */
import { Fragment, useMemo, useState } from 'react';
import { ActionIcon, Menu, Text } from '@mantine/core';
import { IconPrinter } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { PrintItem, usePrintProviders } from '@/shared/extensions/print';

interface PrintButtonProps {
  model: string;
  recordId: number | string;
}

const NO_ITEMS: PrintItem[] = [];

export function PrintButton({ model, recordId }: PrintButtonProps) {
  const { t } = useTranslation('common');
  const providers = usePrintProviders();
  const [itemsByProvider, setItemsByProvider] = useState<
    Record<string, PrintItem[]>
  >({});

  // Стабильный колбэк на провайдера: его эффект зависит от onItems
  const setters = useMemo(
    () =>
      Object.fromEntries(
        providers.map(([key]) => [
          key,
          (items: PrintItem[]) =>
            setItemsByProvider(prev =>
              prev[key] === items ? prev : { ...prev, [key]: items },
            ),
        ]),
      ) as Record<string, (items: PrintItem[]) => void>,
    [providers],
  );

  const items = useMemo(
    () => providers.flatMap(([key]) => itemsByProvider[key] ?? NO_ITEMS),
    [providers, itemsByProvider],
  );

  // Группы в порядке появления; пункты без группы — первыми
  const groups = useMemo(() => {
    const map = new Map<string, PrintItem[]>();
    for (const item of items) {
      const key = item.group ?? '';
      map.set(key, [...(map.get(key) ?? []), item]);
    }
    return Array.from(map.entries());
  }, [items]);

  const collectors = providers.map(([key, Provider]) => (
    <Provider
      key={key}
      model={model}
      recordId={recordId}
      onItems={setters[key]}
    />
  ));

  if (items.length === 0) return <>{collectors}</>;

  const single = items.length === 1 ? items[0] : null;
  // Как соседние иконки тулбара (панели, переключатель вида): subtle md
  const button = (
    <ActionIcon
      variant="subtle"
      color="blue"
      size="md"
      title={t('print')}
      aria-label={t('print')}
      onClick={single ? single.onSelect : undefined}>
      <IconPrinter size={18} />
    </ActionIcon>
  );

  return (
    <>
      {collectors}
      {single ? (
        button
      ) : (
        <Menu
          shadow="md"
          width={240}
          position="bottom-end"
          // Длинные названия — с многоточием: flex-подпись пункта иначе
          // растягивается под текст и вылезает за меню
          styles={{ itemLabel: { minWidth: 0 } }}>
          <Menu.Target>{button}</Menu.Target>
          <Menu.Dropdown>
            {groups.map(([group, list], index) => (
              <Fragment key={group || 'main'}>
                {index > 0 && <Menu.Divider />}
                {group && <Menu.Label>{group}</Menu.Label>}
                {list.map(item => (
                  <Menu.Item
                    key={item.key}
                    leftSection={item.icon}
                    title={item.label}
                    onClick={item.onSelect}>
                    <Text size="sm" truncate>
                      {item.label}
                    </Text>
                  </Menu.Item>
                ))}
              </Fragment>
            ))}
          </Menu.Dropdown>
        </Menu>
      )}
    </>
  );
}
