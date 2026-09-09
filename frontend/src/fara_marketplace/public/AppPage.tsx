import { useState } from 'react';
import {
  Anchor,
  Badge,
  Button,
  Center,
  Grid,
  Group,
  Loader,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconBrandGithub, IconDownload } from '@tabler/icons-react';
import { Link, useParams } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { selectCurrentSession, selectIsLoggedIn } from '@/slices/authSlice';
import {
  marketDownloadUrl,
  marketFreeDownloadUrl,
  marketImageUrl,
  useBuyMarketAppMutation,
  useGetMarketAppQuery,
} from '../api';
import { VendorCheck, VerifiedBadge, formatPrice } from './AppCard';
import { MarketHeader } from './MarketHeader';
import classes from './market.module.css';

/** Страница приложения: описание, скриншоты, покупка/скачивание. */
export default function AppPage() {
  const { id } = useParams<{ id: string }>();
  const appId = Number(id);
  const { t } = useTranslation('marketplace');
  const authenticated = useSelector(selectIsLoggedIn);
  const session = useSelector(selectCurrentSession);

  const { data, isLoading } = useGetMarketAppQuery(appId, { skip: !appId });
  const [buy, { isLoading: buying }] = useBuyMarketAppMutation();
  // Покупка состоялась в этой сессии страницы (уже оплаченное) —
  // показываем кнопку скачивания вместо покупки.
  const [bought, setBought] = useState(false);
  // Активный скриншот в галерее.
  const [activeShot, setActiveShot] = useState(0);

  const app = data?.data;

  const handleBuy = async () => {
    const result = await buy(appId).unwrap();
    if (result.data.payment_url) {
      // Платное: уходим на страницу оплаты провайдера. Вернёт в «Мои покупки».
      window.location.href = result.data.payment_url;
      return;
    }
    setBought(true);
  };

  let content;
  if (isLoading) {
    content = (
      <Center py="xl">
        <Loader />
      </Center>
    );
  } else if (!app) {
    content = (
      <Text ta="center" c="dimmed" py="xl">
        {t('public.notFound')}
      </Text>
    );
  } else {
    const isFree = app.price <= 0;
    const isVendor = !!app.vendor && session?.user_id?.id === app.vendor.id;
    // Платный архив дают купившему или поставщику; бесплатный — всем.
    const canDownloadPaid = bought || isVendor;
    const activeIndex = Math.min(
      activeShot,
      Math.max(app.screenshots.length - 1, 0),
    );

    content = (
      <>
        {/* Сетка: телефон — описание, под ним цена и кнопка; десктоп — 8/4. */}
        <Grid mt="md">
          <Grid.Col span={{ base: 12, md: 8 }}>
            <Title order={1} fz={{ base: 'h2', sm: 'h1' }}>
              {app.name}
            </Title>
            {app.summary && <Text c="dimmed">{app.summary}</Text>}
            <Group gap="xs" mt="xs">
              {app.verified && <VerifiedBadge />}
              <Badge variant="light" color="gray">
                {t(`categories.${app.category}`, app.category)}
              </Badge>
              <Text size="sm" c="dimmed">
                {app.vendor?.name} {app.vendor?.verified && <VendorCheck />} · v
                {app.version} ·{' '}
                {t('public.downloads', { count: app.downloads })}
              </Text>
              {app.source_url && (
                <Anchor
                  href={app.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  size="sm">
                  <IconBrandGithub
                    size={14}
                    style={{ verticalAlign: 'middle' }}
                  />{' '}
                  {t('public.github')}
                </Anchor>
              )}
            </Group>
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 4 }}>
            <Stack gap="xs" className={classes.buyBox}>
              <Text className={classes.price} fz={28}>
                {formatPrice(app.price, t)}
              </Text>

              {/* Бесплатный — скачивается сразу, без входа. */}
              {isFree && (
                <Button
                  component="a"
                  href={marketFreeDownloadUrl(app.id)}
                  leftSection={<IconDownload size={16} />}
                  className={classes.btnPrimary}>
                  {t('public.download')}
                </Button>
              )}

              {/* Платный: вход → покупка → скачивание. */}
              {!isFree && !authenticated && (
                <Button
                  component={Link}
                  to="/login"
                  className={classes.btnPrimary}>
                  {t('public.signInToBuy')}
                </Button>
              )}
              {!isFree && authenticated && canDownloadPaid && (
                <Button
                  component="a"
                  href={marketDownloadUrl(app.id)}
                  leftSection={<IconDownload size={16} />}
                  className={classes.btnPrimary}>
                  {t('public.download')}
                </Button>
              )}
              {!isFree && authenticated && !canDownloadPaid && (
                <>
                  <Button
                    onClick={handleBuy}
                    loading={buying}
                    className={classes.btnPrimary}>
                    {t('public.buy')}
                  </Button>
                  <Text size="xs" c="dimmed">
                    {t('public.purchasesHint')}
                  </Text>
                </>
              )}
            </Stack>
          </Grid.Col>
        </Grid>

        {app.screenshots.length > 0 && (
          <div className={classes.gallery}>
            {/* Крупный кадр — клик открывает оригинал в новой вкладке. */}
            <a
              href={marketImageUrl(app.id, app.screenshots[activeIndex].id)}
              target="_blank"
              rel="noopener noreferrer">
              <img
                className={classes.galleryMain}
                src={marketImageUrl(
                  app.id,
                  app.screenshots[activeIndex].id,
                  1200,
                )}
                alt={app.screenshots[activeIndex].name}
              />
            </a>
            {app.screenshots.length > 1 && (
              <div className={classes.thumbs}>
                {app.screenshots.map((shot, i) => (
                  <img
                    key={shot.id}
                    className={`${classes.thumb} ${
                      i === activeIndex ? classes.thumbActive : ''
                    }`}
                    src={marketImageUrl(app.id, shot.id, 200, 130)}
                    alt={shot.name}
                    onClick={() => setActiveShot(i)}
                    loading="lazy"
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {app.description && (
          <Text className={classes.description} mt="xl">
            {app.description}
          </Text>
        )}
      </>
    );
  }

  return (
    <div className={classes.root}>
      <MarketHeader />
      <div className={classes.container}>
        <Anchor component={Link} to="/market" size="sm">
          ← {t('public.backToCatalog')}
        </Anchor>
        {content}
      </div>
    </div>
  );
}
