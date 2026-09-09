import { Badge, Button, Group, Text, Tooltip } from '@mantine/core';
import {
  IconDownload,
  IconShieldCheck,
  IconUserCheck,
} from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { marketFreeDownloadUrl, marketImageUrl, type MarketApp } from '../api';
import classes from './market.module.css';

export function formatPrice(price: number, t: TFunction): string {
  return price > 0
    ? t('public.price', { price: price.toLocaleString('ru-RU') })
    : t('public.free');
}

/** Отметка «проверено администрацией» у модуля. */
export function VerifiedBadge() {
  const { t } = useTranslation('marketplace');
  return (
    <Badge
      variant="light"
      color="teal"
      leftSection={<IconShieldCheck size={12} />}>
      {t('public.verified')}
    </Badge>
  );
}

/** Галочка у имени подтверждённого продавца. */
export function VendorCheck() {
  const { t } = useTranslation('marketplace');
  return (
    <Tooltip label={t('public.verifiedVendor')}>
      <IconUserCheck
        size={14}
        color="var(--mp-accent)"
        style={{ verticalAlign: 'middle' }}
      />
    </Tooltip>
  );
}

export function AppCard({ app }: { app: MarketApp }) {
  const { t } = useTranslation('marketplace');
  const free = app.price <= 0;

  return (
    <div className={classes.card}>
      {/* Кликабельная часть — переход на страницу модуля. Кнопка внизу
          отдельным элементом, чтобы не вкладывать ссылку в ссылку. */}
      <Link to={`/market/${app.id}`} className={classes.cardLink}>
        {app.cover_id ? (
          <img
            className={classes.cover}
            src={marketImageUrl(app.id, app.cover_id, 640, 360)}
            alt={app.name}
            loading="lazy"
          />
        ) : (
          <div className={classes.coverPlaceholder}>
            {app.name.slice(0, 1).toUpperCase()}
          </div>
        )}
        <div className={classes.cardBody}>
          <Group justify="space-between" align="flex-start" wrap="nowrap">
            <h3 className={classes.cardTitle}>{app.name}</h3>
            <Group gap={4} wrap="nowrap" style={{ flexShrink: 0 }}>
              {app.verified && <VerifiedBadge />}
              <Badge variant="light" color="gray">
                {t(`categories.${app.category}`, app.category)}
              </Badge>
            </Group>
          </Group>
          <p className={classes.cardText}>{app.summary}</p>
          <Text size="xs" c="dimmed" truncate>
            {app.vendor?.name} {app.vendor?.verified && <VendorCheck />} · v
            {app.version} · {t('public.downloads', { count: app.downloads })}
          </Text>
        </div>
      </Link>

      <div className={classes.cardFooter}>
        <span className={classes.price}>{formatPrice(app.price, t)}</span>
        {free ? (
          // Бесплатный — качается сразу, без входа (Content-Disposition).
          <Button
            component="a"
            href={marketFreeDownloadUrl(app.id)}
            leftSection={<IconDownload size={14} />}
            size="compact-sm"
            variant="light"
            color="teal">
            {t('public.download')}
          </Button>
        ) : (
          // Платный — покупка на странице модуля (после входа).
          <Button
            component={Link}
            to={`/market/${app.id}`}
            size="compact-sm"
            variant="light"
            color="teal">
            {t('public.buy')}
          </Button>
        )}
      </div>
    </div>
  );
}
