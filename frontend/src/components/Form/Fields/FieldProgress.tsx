import { useState } from 'react';
import { Group, Progress, Slider, Text } from '@mantine/core';
import { useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

/** Высота полосы: mantine-размер ('xs'…'xl') или пиксели. */
type ProgressSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | number;

interface FieldProgressProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  /** Высота полосы. По умолчанию 'xl'; для крупного бара — число, напр. 24. */
  size?: ProgressSize;
  /** Шаг перетаскивания. По умолчанию 5 %. */
  step?: number;
  /**
   * Можно ли менять значение мышью. По умолчанию true (ползунок).
   * false — только показ: так подключаются вычисляемые поля
   * (Lead.progress / Sale.progress считаются по стадии на бэке).
   */
  editable?: boolean;
  [key: string]: any;
}

/** Цвет по величине: старт — оранжевый, середина — синий, финиш — зелёный. */
const progressColor = (value: number) => {
  if (value >= 100) return 'teal';
  if (value >= 50) return 'blue';
  return 'orange';
};

const clamp = (raw: unknown) => {
  const num = Number(raw ?? 0);
  return Number.isFinite(num) ? Math.max(0, Math.min(100, num)) : 0;
};

interface ProgressSliderProps {
  value: number;
  size: ProgressSize;
  step: number;
  disabled?: boolean;
  onCommit: (value: number) => void;
}

/**
 * Редактируемый ползунок. Отдельный компонент, потому что во время
 * перетаскивания нужно своё состояние (форма uncontrolled и о промежуточных
 * значениях не знает), а монтируется он по form.key(name) — так значение
 * извне (загрузка записи, /onchange) сбрасывает локальное.
 */
const ProgressSlider = ({
  value,
  size,
  step,
  disabled,
  onCommit,
}: ProgressSliderProps) => {
  const [current, setCurrent] = useState(value);

  return (
    <Group gap="xs" wrap="nowrap">
      <Slider
        value={current}
        onChange={setCurrent}
        onChangeEnd={onCommit}
        min={0}
        max={100}
        step={step}
        size={size}
        color={progressColor(current)}
        label={v => `${v}%`}
        disabled={disabled}
        style={{ flex: 1 }}
      />
      <Text size="sm" c="dimmed" style={{ minWidth: 38, textAlign: 'right' }}>
        {current}%
      </Text>
    </Group>
  );
};

/**
 * Поле-процент (0–100) полосой прогресса.
 *
 * Подключение: <Field name="progress" widget="progress" />
 *   editable={false} — только показ (вычисляемые поля);
 *   size={24}        — высота полосы;
 *   step={1}         — шаг ползунка.
 */
export const FieldProgress = ({
  name,
  label,
  labelPosition,
  required,
  size = 'xl',
  step = 5,
  editable = true,
}: FieldProgressProps) => {
  const form = useFormContext();
  const displayLabel = label ?? name;
  // disabled приходит из enhanceGetInputProps формы (поля заблокированы,
  // пока не пришли метаданные) — в типах Mantine этого свойства нет.
  const { disabled } = form.getInputProps(name) as { disabled?: boolean };
  const value = clamp(form.getValues()?.[name]);

  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}
      align="center">
      {editable ? (
        <ProgressSlider
          key={form.key(name)}
          value={value}
          size={size}
          step={step}
          disabled={disabled}
          onCommit={next => form.setFieldValue(name, next)}
        />
      ) : (
        <Group gap="xs" wrap="nowrap" key={form.key(name)}>
          <Progress
            value={value}
            color={progressColor(value)}
            size={size}
            radius="xl"
            aria-label={displayLabel}
            style={{ flex: 1 }}
          />
          <Text
            size="sm"
            c="dimmed"
            style={{ minWidth: 38, textAlign: 'right' }}>
            {value}%
          </Text>
        </Group>
      )}
    </FieldWrapper>
  );
};
