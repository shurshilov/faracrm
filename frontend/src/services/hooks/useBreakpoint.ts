import { useMediaQuery } from '@mantine/hooks';

/**
 * Хук для определения текущего брейкпоинта.
 * Использует Mantine breakpoints: base(<576), sm(576), md(768), lg(992), xl(1200)
 *
 * Mobile-first: isMobile = true на экранах < 576px
 *
 * @example
 * const { isMobile, isTablet, isDesktop } = useBreakpoint();
 * // isMobile: < 576px
 * // isTablet: 576–991px
 * // isDesktop: >= 992px
 */
export function useBreakpoint() {
  const isMobile = useMediaQuery('(max-width: 575px)');
  const isTablet = useMediaQuery('(min-width: 576px) and (max-width: 991px)');
  const isDesktop = useMediaQuery('(min-width: 992px)');
  const isLargeDesktop = useMediaQuery('(min-width: 1200px)');

  return {
    isMobile: isMobile ?? false,
    isTablet: isTablet ?? false,
    isDesktop: isDesktop ?? false,
    isLargeDesktop: isLargeDesktop ?? false,
  };
}
