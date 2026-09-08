import { Badge, Group, Text, Tooltip } from '@mantine/core';
import { IconShieldCheck, IconUserCheck } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { marketImageUrl, type MarketApp } from '../api';
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

  return (
    <Link to={`/market/${app.id}`} className={classes.card}>
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
        <Group justify="space-between" wrap="nowrap">
          <Text size="xs" c="dimmed" truncate>
            {app.vendor?.name} {app.vendor?.verified && <VendorCheck />} · v
            {app.version} · {t('public.downloads', { count: app.downloads })}
          </Text>
          <span className={classes.price}>{formatPrice(app.price, t)}</span>
        </Group>
      </div>
    </Link>
  );
}
