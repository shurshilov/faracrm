import { useEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { Text, Tooltip } from '@mantine/core';
import type { TextProps } from '@mantine/core';

/** Допуск при сравнении размеров: дробная высота строки даёт доли пикселя. */
const OVERFLOW_TOLERANCE = 1;

export interface TruncatedTextProps {
  /** Полный текст: показывается обрезанным, целиком уходит в подсказку. */
  text: string;
  /**
   * Сколько строк показывать до обрезки: 1 — обычная строка карточки,
   * 2 — название записи (issue #79).
   */
  lines?: 1 | 2;
  /** Размер шрифта Mantine (у полей карточки — sm). */
  size?: TextProps['size'];
  /** Насыщенность (у названия карточки — 500). */
  fw?: TextProps['fw'];
  /** Цвет текста (у полей карточки — dimmed). */
  c?: TextProps['c'];
  className?: string;
  /** Доп. стили текста — например, `flex: 1` в строке «иконка + текст». */
  style?: CSSProperties;
}

/**
 * Текст, обрезанный «…» по одной или двум строкам, с подсказкой полного
 * текста при наведении — для карточек канбана.
 *
 * Обрезку делает Mantine, а этот компонент лишь решает, показывать ли
 * подсказку: она нужна только там, где текст реально не влез, иначе
 * всплывала бы на каждой строке карточки.
 *
 * Одну строку режем через `truncate` (white-space: nowrap; overflow: hidden):
 * лишний текст вылезает по ширине, и обрезка видна по scrollWidth.
 * У нескольких строк обрезку делает `-webkit-line-clamp`, но полагаться на
 * scrollHeight нельзя: в Chrome он равен высоте обрезки, а не содержимого.
 * Поэтому реальное число строк считаем Range'ом — он отдаёт прямоугольники
 * всех строк текста, включая скрытые clamp'ом; scrollHeight оставлен
 * запасной проверкой для старых движков.
 */
export function TruncatedText({
  text,
  lines = 1,
  size,
  fw,
  c,
  className,
  style,
}: TruncatedTextProps) {
  const ref = useRef<HTMLParagraphElement>(null);
  const [clipped, setClipped] = useState(false);
  // Одна строка — как в ячейке списка: nowrap + «…» на конце. Две — clamp.
  const clampProps = lines === 1 ? { truncate: true } : { lineClamp: lines };

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const measure = () => {
      if (lines === 1) {
        setClipped(node.scrollWidth - node.clientWidth > OVERFLOW_TOLERANCE);
        return;
      }

      const range = document.createRange();
      range.selectNodeContents(node);
      const lineCount = range.getClientRects().length;

      setClipped(
        lineCount > lines ||
          node.scrollHeight - node.clientHeight > OVERFLOW_TOLERANCE,
      );
    };

    measure();

    // Ширина колонки меняется на мобильной вёрстке и при зуме, а шрифт может
    // догрузиться позже — пересчитываем по ResizeObserver.
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [text, lines]);

  return (
    <Tooltip
      label={text}
      multiline
      maw={340}
      withArrow
      openDelay={300}
      disabled={!clipped}
      style={{ overflowWrap: 'anywhere' }}>
      <Text
        ref={ref}
        size={size}
        fw={fw}
        c={c}
        className={className}
        style={style}
        {...clampProps}>
        {text}
      </Text>
    </Tooltip>
  );
}

export default TruncatedText;
