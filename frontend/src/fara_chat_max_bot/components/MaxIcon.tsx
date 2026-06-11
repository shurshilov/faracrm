import maxIconUrl from '../assets/max.svg';

/**
 * Иконка мессенджера MAX (МАКС).
 *
 * SVG-логотип отдаётся как URL (проект резолвит *.svg в строку), поэтому
 * рендерим через <img>. Принимает `size`, чтобы совпадать с интерфейсом
 * tabler-иконок и использоваться в темах/переключателях коннекторов.
 */
export function MaxIcon({ size = 16 }: { size?: number }) {
  return (
    <img
      src={maxIconUrl}
      width={size}
      height={size}
      alt="MAX"
      draggable={false}
      style={{ display: 'block' }}
    />
  );
}

export default MaxIcon;
