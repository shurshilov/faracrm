import { Badge, Group, Text } from '@mantine/core';
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
          <Badge variant="light" color="gray" style={{ flexShrink: 0 }}>
            {t(`categories.${app.category}`, app.category)}
          </Badge>
        </Group>
        <p className={classes.cardText}>{app.summary}</p>
        <Group justify="space-between" wrap="nowrap">
          <Text size="xs" c="dimmed" truncate>
            {app.vendor?.name} · v{app.version} ·{' '}
            {t('public.downloads', { count: app.downloads })}
          </Text>
          <span className={classes.price}>{formatPrice(app.price, t)}</span>
        </Group>
      </div>
    </Link>
  );
}
