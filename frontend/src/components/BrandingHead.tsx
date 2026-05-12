import { useEffect, useRef } from 'react';
import {
  useGetPublicConfigQuery,
  brandingFileUrl,
} from '@/services/config/config';

/**
 * Динамическая подмена favicon, <title> и PWA-манифеста под
 * настройки текущей компании (поля favicon_id / app_title в Company).
 *
 * Как это вообще работает (отвечает на вопрос «ведь это берётся из index.html»):
 * — index.html выдаётся статикой и в нём только дефолтные значения
 *   (<title>F.A.R.A.</title>, <link rel="icon" href="/logo-mark.svg">,
 *   <link rel="manifest" href="/manifest.json">).
 * — После загрузки JS этот компонент уже в рантайме редактирует те же
 *   теги в <head>: document.title, href у link[rel=icon] и link[rel=manifest].
 *   Браузер подхватывает новые значения сразу (вкладка/favicon).
 * — Для PWA генерируется новый manifest как Blob-URL: туда подставляем
 *   app_title в name/short_name и URL фавикона в icons[*].src. Браузер
 *   читает manifest при /показе/ установки PWA, поэтому для новых установок
 *   значения будут уже кастомные.
 *
 * Что НЕ изменится:
 * — Уже установленные PWA. ОС кеширует name/icon на момент установки,
 *   юзеру придётся переустановить (или удалить ярлык) чтобы подхватить новый.
 * — og:title и др. SEO-теги — поисковики/соцсети читают серверный HTML
 *   до выполнения JS. Если нужна полноценная SEO-подмена, делать на бэке.
 */
export function BrandingHead() {
  const { data: publicConfig } = useGetPublicConfigQuery();
  const blobUrlRef = useRef<string | null>(null);

  useEffect(() => {
    const branding = publicConfig?.branding;
    if (!branding) return;

    // ---- 1. <title> ----------------------------------------------------
    const title = branding.app_title?.trim();
    if (title) {
      document.title = title;
    }

    // ---- 2. Favicon (link[rel=icon] + apple-touch-icon) ----------------
    // Если на бэке есть favicon — подсовываем его во все link-теги иконок.
    // Иначе оставляем то, что прописано в index.html.
    if (branding.has_favicon) {
      const url = brandingFileUrl('favicon_id');
      setIconHref('icon', url);
      setIconHref('shortcut icon', url);
      setIconHref('apple-touch-icon', url);
    }

    // ---- 3. PWA-манифест -----------------------------------------------
    // Подменяем только если есть что менять (имя или иконка).
    if (title || branding.has_favicon) {
      const iconUrl = branding.has_favicon
        ? toAbsoluteUrl(brandingFileUrl('favicon_id'))
        : null;

      // Дефолты из /manifest.json — иначе у браузера может «съехать»
      // background_color/theme_color. Берём только то, что патчим.
      const manifest: Record<string, unknown> = {
        name: title || 'FARA CRM',
        short_name: title || 'FARA',
        description: 'FARA CRM - Customer Relationship Management',
        start_url: '/',
        display: 'standalone',
        background_color: '#ffffff',
        theme_color: '#228be6',
        icons: iconUrl
          ? [
              {
                src: iconUrl,
                sizes: '192x192',
                type: 'image/png',
                purpose: 'any',
              },
              {
                src: iconUrl,
                sizes: '512x512',
                type: 'image/png',
                purpose: 'any maskable',
              },
            ]
          : [
              {
                src: '/icon-192.png',
                sizes: '192x192',
                type: 'image/png',
                purpose: 'any maskable',
              },
              {
                src: '/icon-512.png',
                sizes: '512x512',
                type: 'image/png',
                purpose: 'any maskable',
              },
            ],
      };

      // Освобождаем предыдущий Blob, если он был (utility hygiene в SPA-навигациях)
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
      }
      const blob = new Blob([JSON.stringify(manifest)], {
        type: 'application/manifest+json',
      });
      const blobUrl = URL.createObjectURL(blob);
      blobUrlRef.current = blobUrl;

      const link = document.querySelector<HTMLLinkElement>(
        'link[rel="manifest"]',
      );
      if (link) {
        link.setAttribute('href', blobUrl);
      } else {
        const created = document.createElement('link');
        created.rel = 'manifest';
        created.href = blobUrl;
        document.head.appendChild(created);
      }
    }
  }, [publicConfig]);

  // Чистим Blob при размонтировании (на практике компонент живёт всю сессию).
  useEffect(() => {
    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, []);

  return null;
}

/**
 * Меняет href у link[rel=<rel>]. Если такого тега нет — создаёт.
 * Параллельно убираем `sizes`, т.к. для произвольной картинки мы их не знаем,
 * а старое значение из index.html может мешать выбору иконки браузером.
 */
function setIconHref(rel: string, href: string) {
  const selector = `link[rel="${rel}"]`;
  const nodes = document.querySelectorAll<HTMLLinkElement>(selector);
  if (nodes.length === 0) {
    const link = document.createElement('link');
    link.rel = rel;
    link.href = href;
    document.head.appendChild(link);
    return;
  }
  nodes.forEach(node => {
    node.setAttribute('href', href);
    node.removeAttribute('type');
    node.removeAttribute('sizes');
  });
}

/**
 * Manifest icons[*].src должен быть абсолютным URL — относительный
 * Blob-URL не понимает «base» документа, и иконку браузер не найдёт.
 */
function toAbsoluteUrl(url: string): string {
  try {
    return new URL(url, window.location.origin).toString();
  } catch {
    return url;
  }
}

export default BrandingHead;
