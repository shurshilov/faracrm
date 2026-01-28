import { useMemo, useCallback, useState, useRef, useEffect } from 'react';
import { Text, Group, Stack, ScrollArea, Tooltip, Box, SegmentedControl, ActionIcon, Button } from '@mantine/core';
import { IconPlus, IconCalendarEvent } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useSearchQuery } from '@/services/api/crudApi';
import { FaraRecord, GetListParams, GetListResult } from '@/services/api/crudTypes';
import {
  BaseQueryFn,
  TypedUseQueryHookResult,
} from '@reduxjs/toolkit/query/react';
import classes from './Gantt.module.css';

export type GanttScale = 'hour' | '2hours' | '4hours' | 'day' | 'week' | 'month';

export interface GanttProps<T extends FaraRecord> {
  model: string;
  fields?: string[];
  // Режим 1: два поля даты
  startField?: string;
  endField?: string;
  // Режим 2: одно поле даты + длительность (в секундах)
  dateField?: string;
  durationField?: string;
  // Название для отображения
  labelField?: string;
  // Цвет плашки
  colorField?: string;
  defaultColor?: string;
  // Начальный масштаб
  defaultScale?: GanttScale;
  // Сортировка
  sort?: string;
  order?: 'asc' | 'desc';
}

interface GanttBar {
  id: number;
  label: string;
  start: Date;
  end: Date;
  color: string;
  record: FaraRecord;
}

interface GanttRow {
  id: number;
  label: string;
  bars: GanttBar[];
  totalDuration: number; // в миллисекундах
}

// Форматирование длительности
function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) {
    return `${days}д ${hours % 24}ч`;
  }
  if (hours > 0) {
    return `${hours}ч ${minutes % 60}м`;
  }
  if (minutes > 0) {
    return `${minutes}м`;
  }
  return `${seconds}с`;
}

// Форматирование даты для тултипа
function formatDateTime(date: Date): string {
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// Генерация цвета из строки
function stringToColor(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = hash % 360;
  return `hsl(${hue}, 70%, 50%)`;
}

// Проверка - выходной день
function isWeekend(date: Date): boolean {
  const day = date.getDay();
  return day === 0 || day === 6;
}

// Получить шаг и ширину ячейки для масштаба
function getScaleConfig(scale: GanttScale) {
  switch (scale) {
    case 'hour':
      return { step: 60 * 60 * 1000, cellWidth: 60, minorStep: 15 * 60 * 1000 };
    case '2hours':
      return { step: 2 * 60 * 60 * 1000, cellWidth: 80, minorStep: 30 * 60 * 1000 };
    case '4hours':
      return { step: 4 * 60 * 60 * 1000, cellWidth: 80, minorStep: 60 * 60 * 1000 };
    case 'day':
      return { step: 24 * 60 * 60 * 1000, cellWidth: 40, minorStep: 6 * 60 * 60 * 1000 };
    case 'week':
      return { step: 7 * 24 * 60 * 60 * 1000, cellWidth: 100, minorStep: 24 * 60 * 60 * 1000 };
    case 'month':
      return { step: 30 * 24 * 60 * 60 * 1000, cellWidth: 120, minorStep: 7 * 24 * 60 * 60 * 1000 };
  }
}

// Форматирование верхнего уровня
function formatMajorLabel(date: Date, scale: GanttScale): string {
  switch (scale) {
    case 'hour':
    case '2hours':
    case '4hours':
      return date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' });
    case 'day':
      return date.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
    case 'week':
      return date.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
    case 'month':
      return date.getFullYear().toString();
  }
}

// Форматирование нижнего уровня
function formatMinorLabel(date: Date, scale: GanttScale): string {
  switch (scale) {
    case 'hour':
    case '2hours':
    case '4hours':
      return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    case 'day':
      return date.getDate().toString();
    case 'week':
      return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
    case 'month':
      return date.toLocaleDateString('ru-RU', { month: 'short' });
  }
}

// Получить ключ для группировки верхнего уровня
function getMajorKey(date: Date, scale: GanttScale): string {
  switch (scale) {
    case 'hour':
    case '2hours':
    case '4hours':
      return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
    case 'day':
    case 'week':
      return `${date.getFullYear()}-${date.getMonth()}`;
    case 'month':
      return date.getFullYear().toString();
  }
}

export function Gantt<T extends FaraRecord>({
  model,
  fields = ['id', 'name'],
  startField,
  endField,
  dateField,
  durationField,
  labelField = 'name',
  colorField,
  defaultColor = '#3498db',
  defaultScale = 'day',
  sort,
  order = 'asc',
}: GanttProps<T>) {
  const navigate = useNavigate();
  const { t } = useTranslation('common');
  const [scale, setScale] = useState<GanttScale>(defaultScale);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [hasScrolled, setHasScrolled] = useState(false);

  // Собираем все нужные поля
  const queryFields = useMemo(() => {
    const allFields = new Set(fields);
    allFields.add('id');
    if (labelField) allFields.add(labelField);
    if (startField) allFields.add(startField);
    if (endField) allFields.add(endField);
    if (dateField) allFields.add(dateField);
    if (durationField) allFields.add(durationField);
    if (colorField) allFields.add(colorField);
    if (sort) allFields.add(sort);
    return Array.from(allFields);
  }, [fields, startField, endField, dateField, durationField, labelField, colorField, sort]);

  // Загрузка данных
  const { data: recordsData } = useSearchQuery({
    model,
    fields: queryFields,
    limit: 500,
    order: order,
    sort: sort || startField || dateField || 'id',
  }) as TypedUseQueryHookResult<GetListResult<T>, GetListParams, BaseQueryFn>;

  const records = recordsData?.data || [];

  // Преобразуем записи в строки с барами
  const rows = useMemo<GanttRow[]>(() => {
    const rowsMap = new Map<number, GanttRow>();

    records.forEach(record => {
      let start: Date | null = null;
      let end: Date | null = null;

      // Режим 1: startField + endField
      if (startField && endField) {
        const startVal = record[startField];
        const endVal = record[endField];
        if (startVal) start = new Date(startVal as string);
        if (endVal) end = new Date(endVal as string);
      }
      // Режим 2: dateField + durationField
      else if (dateField && durationField) {
        const dateVal = record[dateField];
        const durationVal = record[durationField];
        if (dateVal) {
          start = new Date(dateVal as string);
          if (durationVal && typeof durationVal === 'number') {
            end = new Date(start.getTime() + durationVal * 1000);
          }
        }
      }

      if (!start || !end) return;

      // Определяем цвет
      let color = defaultColor;
      if (colorField && record[colorField]) {
        const colorVal = record[colorField];
        if (typeof colorVal === 'string' && colorVal.startsWith('#')) {
          color = colorVal;
        } else {
          color = stringToColor(String(colorVal));
        }
      }

      // Определяем label
      const labelVal = record[labelField];
      const label = typeof labelVal === 'object' && labelVal?.name
        ? labelVal.name
        : String(labelVal || `#${record.id}`);

      const bar: GanttBar = {
        id: record.id,
        label,
        start,
        end,
        color,
        record,
      };

      // Группируем по id записи
      if (rowsMap.has(record.id)) {
        const row = rowsMap.get(record.id)!;
        row.bars.push(bar);
        row.totalDuration += end.getTime() - start.getTime();
      } else {
        rowsMap.set(record.id, {
          id: record.id,
          label,
          bars: [bar],
          totalDuration: end.getTime() - start.getTime(),
        });
      }
    });

    return Array.from(rowsMap.values());
  }, [records, startField, endField, dateField, durationField, labelField, colorField, defaultColor]);

  // Вычисляем временной диапазон
  const { minTime, maxTime } = useMemo(() => {
    if (rows.length === 0) {
      const now = new Date();
      return {
        minTime: now,
        maxTime: new Date(now.getTime() + 24 * 60 * 60 * 1000),
      };
    }

    let min = Infinity;
    let max = -Infinity;

    rows.forEach(row => {
      row.bars.forEach(bar => {
        if (bar.start.getTime() < min) min = bar.start.getTime();
        if (bar.end.getTime() > max) max = bar.end.getTime();
      });
    });

    // Выравниваем по началу дня/часа в зависимости от масштаба
    const { step } = getScaleConfig(scale);
    min = Math.floor(min / step) * step;
    max = Math.ceil(max / step) * step + step;

    return {
      minTime: new Date(min),
      maxTime: new Date(max),
    };
  }, [rows, scale]);

  // Генерируем временную шкалу
  const { majorCells, minorCells, totalWidth } = useMemo(() => {
    const { step, cellWidth } = getScaleConfig(scale);
    const minorCells: { time: Date; label: string; isWeekend: boolean; left: number }[] = [];
    const majorCellsMap = new Map<string, { label: string; startLeft: number; endLeft: number }>();

    // Подсветка выходных только для масштабов где видны дни
    const showWeekends = scale === 'hour' || scale === '2hours' || scale === '4hours' || scale === 'day';

    let current = new Date(minTime);
    let left = 0;

    while (current.getTime() <= maxTime.getTime()) {
      const majorKey = getMajorKey(current, scale);
      const isWknd = showWeekends && isWeekend(current);

      minorCells.push({
        time: new Date(current),
        label: formatMinorLabel(current, scale),
        isWeekend: isWknd,
        left,
      });

      if (!majorCellsMap.has(majorKey)) {
        majorCellsMap.set(majorKey, {
          label: formatMajorLabel(current, scale),
          startLeft: left,
          endLeft: left + cellWidth,
        });
      } else {
        majorCellsMap.get(majorKey)!.endLeft = left + cellWidth;
      }

      current = new Date(current.getTime() + step);
      left += cellWidth;
    }

    return {
      minorCells,
      majorCells: Array.from(majorCellsMap.values()),
      totalWidth: left,
    };
  }, [minTime, maxTime, scale]);

  const handleBarClick = useCallback((id: number) => {
    navigate(`${id}`);
  }, [navigate]);

  const handleCreate = useCallback(() => {
    navigate('create');
  }, [navigate]);

  // Скролл к текущей дате или последней записи
  const scrollToNow = useCallback(() => {
    if (!viewportRef.current || totalWidth === 0) return;

    const now = new Date();
    let targetTime = now.getTime();
    
    // Если текущая дата за пределами данных
    if (now.getTime() > maxTime.getTime()) {
      let maxEnd = minTime.getTime();
      rows.forEach(row => {
        row.bars.forEach(bar => {
          if (bar.end.getTime() > maxEnd) maxEnd = bar.end.getTime();
        });
      });
      targetTime = maxEnd;
    } else if (now.getTime() < minTime.getTime()) {
      targetTime = minTime.getTime();
    }

    const totalDuration = maxTime.getTime() - minTime.getTime();
    if (totalDuration <= 0) return;
    
    const scrollPosition = ((targetTime - minTime.getTime()) / totalDuration) * totalWidth;
    const viewportWidth = viewportRef.current.clientWidth;
    const scrollLeft = Math.max(0, Math.min(scrollPosition - viewportWidth / 2, totalWidth - viewportWidth));
    
    viewportRef.current.scrollTo({ left: scrollLeft, behavior: 'smooth' });
  }, [minTime, maxTime, totalWidth, rows]);

  // Вычисляем позицию и ширину бара
  const getBarStyle = useCallback((bar: GanttBar) => {
    const { cellWidth, step } = getScaleConfig(scale);
    const totalDuration = maxTime.getTime() - minTime.getTime();
    const left = ((bar.start.getTime() - minTime.getTime()) / totalDuration) * totalWidth;
    const width = ((bar.end.getTime() - bar.start.getTime()) / totalDuration) * totalWidth;
    return {
      left: `${left}px`,
      width: `${Math.max(width, 4)}px`,
      backgroundColor: bar.color,
    };
  }, [minTime, maxTime, totalWidth, scale]);

  const scaleOptions = [
    { value: 'hour', label: '1ч' },
    { value: '2hours', label: '2ч' },
    { value: '4hours', label: '4ч' },
    { value: 'day', label: 'День' },
    { value: 'week', label: 'Неделя' },
    { value: 'month', label: 'Месяц' },
  ];

  const { cellWidth } = getScaleConfig(scale);

  // Автоскролл к текущей дате или последней записи
  useEffect(() => {
    if (hasScrolled || rows.length === 0 || totalWidth === 0) return;

    // Небольшая задержка чтобы DOM успел отрендериться
    const timer = setTimeout(() => {
      if (!viewportRef.current) return;
      
      // Определяем целевую дату: текущая или последняя запись
      const now = new Date();
      let targetTime = now.getTime();
      
      // Если текущая дата за пределами данных, скроллим к последней записи
      if (now.getTime() > maxTime.getTime()) {
        // Находим максимальную дату окончания
        let maxEnd = minTime.getTime();
        rows.forEach(row => {
          row.bars.forEach(bar => {
            if (bar.end.getTime() > maxEnd) maxEnd = bar.end.getTime();
          });
        });
        targetTime = maxEnd;
      } else if (now.getTime() < minTime.getTime()) {
        targetTime = minTime.getTime();
      }

      // Вычисляем позицию скролла
      const totalDuration = maxTime.getTime() - minTime.getTime();
      if (totalDuration <= 0) return;
      
      const scrollPosition = ((targetTime - minTime.getTime()) / totalDuration) * totalWidth;
      
      // Центрируем в видимой области (или скроллим к концу если цель справа)
      const viewportWidth = viewportRef.current.clientWidth;
      const scrollLeft = Math.max(0, Math.min(scrollPosition - viewportWidth / 2, totalWidth - viewportWidth));
      
      viewportRef.current.scrollTo({ left: scrollLeft, behavior: 'instant' });
      setHasScrolled(true);
    }, 200);

    return () => clearTimeout(timer);
  }, [rows, minTime, maxTime, totalWidth, hasScrolled]);

  // Сброс флага скролла при смене масштаба
  useEffect(() => {
    setHasScrolled(false);
  }, [scale]);

  return (
    <div className={classes.container}>
      {/* Панель управления */}
      <div className={classes.toolbar}>
        <Group justify="space-between">
          <Group gap="xs">
            <Button
              leftSection={<IconPlus size={16} />}
              size="xs"
              onClick={handleCreate}
            >
              {t('create', 'Создать')}
            </Button>
            <Button
              leftSection={<IconCalendarEvent size={16} />}
              size="xs"
              variant="light"
              onClick={scrollToNow}
            >
              {t('gantt.today', 'Сегодня')}
            </Button>
          </Group>
          <SegmentedControl
            size="xs"
            value={scale}
            onChange={(value) => setScale(value as GanttScale)}
            data={scaleOptions}
          />
        </Group>
      </div>

      <div className={classes.ganttWrapper}>
        {/* Фиксированная левая колонка */}
        <div className={classes.leftPanel}>
          {/* Заголовки левой панели */}
          <div className={classes.leftHeader}>
            <div className={classes.labelColumn}>
              <Text fw={600} size="sm">{t('gantt.name', 'Название')}</Text>
            </div>
            <div className={classes.durationColumn}>
              <Text fw={600} size="sm">{t('gantt.duration', 'Время')}</Text>
            </div>
          </div>
          {/* Строки левой панели */}
          <div className={classes.leftBody}>
            {rows.map(row => (
              <div key={row.id} className={classes.leftRow}>
                <div className={classes.labelColumn}>
                  <Text size="sm" truncate>{row.label}</Text>
                </div>
                <div className={classes.durationColumn}>
                  <Text size="xs" c="dimmed">{formatDuration(row.totalDuration)}</Text>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Скроллируемая область с таймлайном */}
        <ScrollArea className={classes.timelineArea} offsetScrollbars type="always" viewportRef={viewportRef}>
          <div className={classes.timelineContent} style={{ width: totalWidth }}>
            {/* Заголовок таймлайна - верхний уровень */}
            <div className={classes.majorHeader}>
              {majorCells.map((cell, i) => (
                <div
                  key={i}
                  className={classes.majorCell}
                  style={{
                    left: cell.startLeft,
                    width: cell.endLeft - cell.startLeft,
                  }}
                >
                  <Text size="xs" fw={500}>{cell.label}</Text>
                </div>
              ))}
            </div>

            {/* Заголовок таймлайна - нижний уровень */}
            <div className={classes.minorHeader}>
              {minorCells.map((cell, i) => (
                <div
                  key={i}
                  className={`${classes.minorCell} ${cell.isWeekend ? classes.weekend : ''}`}
                  style={{
                    left: cell.left,
                    width: cellWidth,
                  }}
                >
                  <Text size="xs">{cell.label}</Text>
                </div>
              ))}
            </div>

            {/* Тело с барами */}
            <div className={classes.timelineBody}>
              {/* Фон с выходными */}
              {minorCells.map((cell, i) => (
                <div
                  key={i}
                  className={`${classes.gridColumn} ${cell.isWeekend ? classes.weekendColumn : ''}`}
                  style={{
                    left: cell.left,
                    width: cellWidth,
                  }}
                />
              ))}

              {/* Строки с барами */}
              {rows.map(row => (
                <div key={row.id} className={classes.timelineRow}>
                  {row.bars.map((bar, i) => (
                    <Tooltip
                      key={i}
                      label={
                        <Stack gap={2}>
                          <Text size="sm" fw={500}>{bar.label}</Text>
                          <Text size="xs">Начало: {formatDateTime(bar.start)}</Text>
                          <Text size="xs">Конец: {formatDateTime(bar.end)}</Text>
                          <Text size="xs">Длительность: {formatDuration(bar.end.getTime() - bar.start.getTime())}</Text>
                        </Stack>
                      }
                      position="top"
                      withArrow
                    >
                      <div
                        className={classes.bar}
                        style={getBarStyle(bar)}
                        onClick={() => handleBarClick(bar.id)}
                      />
                    </Tooltip>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </ScrollArea>
      </div>

      {rows.length === 0 && (
        <div className={classes.empty}>
          <Text c="dimmed">Нет данных для отображения</Text>
        </div>
      )}
    </div>
  );
}
