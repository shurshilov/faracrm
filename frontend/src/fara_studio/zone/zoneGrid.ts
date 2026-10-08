/**
 * Сетка зоны «Дополнительно»: поле стоит левым верхним углом в клетке
 * (x — колонка, y — строка) и занимает w × h клеток, всё с 1. Обычный
 * CSS grid (ExtraGrid); здесь — раскладка и проверки без React, общие для
 * формы и редактора студии.
 */

/** Где зона: под формой, колонкой справа, вкладкой. */
export type ExtraPlacement = 'bottom' | 'side' | 'tab';

export const EXTRA_PLACEMENTS: ExtraPlacement[] = ['bottom', 'side', 'tab'];

export interface ExtraGridSize {
  columns: number;
  /** null — строк сколько понадобится. */
  rows: number | null;
}

/** Клетка как сохранена: без x/y — в первую свободную. */
export interface StoredCell {
  name: string;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
}

/** Поле на своём месте в сетке. */
export interface ExtraCell {
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Клетки из JSON-массива настроек; битое значение — пусто. */
export function parseCells(raw: string | null | undefined): StoredCell[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter(
          (cell): cell is StoredCell => typeof cell?.name === 'string',
        )
      : [];
  } catch {
    return [];
  }
}

function overlaps(a: ExtraCell, b: ExtraCell): boolean {
  return (
    a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
  );
}

/** Поле влезает в сетку и не накрывает других полей. */
export function fits(
  cell: ExtraCell,
  others: ExtraCell[],
  size: ExtraGridSize,
): boolean {
  if (cell.x < 1 || cell.y < 1) return false;
  if (cell.x + cell.w - 1 > size.columns) return false;
  if (size.rows && cell.y + cell.h - 1 > size.rows) return false;
  return !others.some(
    other => other.name !== cell.name && overlaps(cell, other),
  );
}

/** Первая свободная клетка по строкам; заданные строки кончились — ниже. */
function firstFree(
  cell: ExtraCell,
  placed: ExtraCell[],
  columns: number,
): { x: number; y: number } {
  const unbounded = { columns, rows: null };
  for (let y = 1; ; y += 1) {
    for (let x = 1; x <= columns; x += 1) {
      if (fits({ ...cell, x, y }, placed, unbounded)) return { x, y };
    }
  }
}

/**
 * Разложить поля по сетке: сохранённое место, если влезает; иначе (нет
 * места, сетку уменьшили, место занято) — первая свободная клетка.
 * Сохранённое не трогаем: вернули колонки — поля вернулись на места.
 * Результат — по строкам, затем колонкам: в этом порядке поля идут на
 * узком экране.
 */
export function placeCells(
  cells: StoredCell[],
  size: ExtraGridSize,
): ExtraCell[] {
  const placed: ExtraCell[] = [];
  const pending: ExtraCell[] = [];
  for (const cell of cells) {
    const full = {
      name: cell.name,
      x: cell.x ?? 0,
      y: cell.y ?? 0,
      w: Math.min(cell.w ?? 1, size.columns),
      h: size.rows ? Math.min(cell.h ?? 1, size.rows) : (cell.h ?? 1),
    };
    (fits(full, placed, size) ? placed : pending).push(full);
  }
  for (const cell of pending) {
    placed.push({ ...cell, ...firstFree(cell, placed, size.columns) });
  }
  return placed.sort((a, b) => a.y - b.y || a.x - b.x);
}

/**
 * Поставить поле (новое — 1×1) левым верхним углом в клетку (x, y).
 * Там другое поле, и оно влезает на прежнее место нашего — меняются
 * местами. Не выходит — null.
 */
export function placeAt(
  cells: ExtraCell[],
  name: string,
  x: number,
  y: number,
  size: ExtraGridSize,
): ExtraCell[] | null {
  const current = cells.find(cell => cell.name === name);
  const moved = { name, w: 1, h: 1, ...current, x, y };
  const others = cells.filter(cell => cell.name !== name);
  if (fits(moved, others, size)) return [...others, moved];

  const hit = others.filter(cell => overlaps(moved, cell));
  if (!current || hit.length !== 1) return null;
  const swapped = { ...hit[0], x: current.x, y: current.y };
  const rest = others.filter(cell => cell !== hit[0]);
  return fits(moved, rest, size) && fits(swapped, [...rest, moved], size)
    ? [...rest, moved, swapped]
    : null;
}

/** Новый размер поля; вылезает за сетку или на соседей — null. */
export function resizeCell(
  cells: ExtraCell[],
  name: string,
  w: number,
  h: number,
  size: ExtraGridSize,
): ExtraCell[] | null {
  const cell = cells.find(item => item.name === name);
  if (!cell) return null;
  const next = { ...cell, w, h };
  return fits(next, cells, size)
    ? cells.map(item => (item.name === name ? next : item))
    : null;
}
