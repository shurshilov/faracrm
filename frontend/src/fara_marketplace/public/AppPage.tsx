import { useState } from 'react';
import {
  Anchor,
  Badge,
  Button,
  Center,
  Grid,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconDownload } from '@tabler/icons-react';
import { Link, useParams } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { selectCurrentSession, selectIsLoggedIn } from '@/slices/authSlice';
import {
  marketDownloadUrl,
  marketImageUrl,
  useBuyMarketAppMutation,
  useGetMarketAppQuery,
} from '../api';
import { formatPrice } from './AppCard';
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
  // Покупка состоялась в этой сессии страницы (бесплатное или уже
  // оплаченное) — показываем кнопку скачивания вместо покупки.
  const [bought, setBought] = useState(false);

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
    const isVendor = !!app.vendor && session?.user_id?.id === app.vendor.id;
    const canDownload = bought || isVendor;

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
              <Badge variant="light" color="gray">
                {t(`categories.${app.category}`, app.category)}
              </Badge>
              <Text size="sm" c="dimmed">
                {app.vendor?.name} · v{app.version} ·{' '}
                {t('public.downloads', { count: app.downloads })}
              </Text>
            </Group>
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 4 }}>
            <Stack gap="xs" className={classes.buyBox}>
              <Text className={classes.price} fz={28}>
                {formatPrice(app.price, t)}
              </Text>
              {!authenticated && (
                <Button
                  component={Link}
                  to="/login"
                  className={classes.btnPrimary}>
                  {t('public.signInToBuy')}
                </Button>
              )}
              {authenticated && canDownload && (
                <Button
                  component="a"
                  href={marketDownloadUrl(app.id)}
                  leftSection={<IconDownload size={16} />}
                  className={classes.btnPrimary}>
                  {t('public.download')}
                </Button>
              )}
              {authenticated && !canDownload && (
                <Button
                  onClick={handleBuy}
                  loading={buying}
                  className={classes.btnPrimary}>
                  {app.price > 0 ? t('public.buy') : t('public.getFree')}
                </Button>
              )}
              {authenticated && !canDownload && app.price > 0 && (
                <Text size="xs" c="dimmed">
                  {t('public.purchasesHint')}
                </Text>
              )}
            </Stack>
          </Grid.Col>
        </Grid>

        {app.screenshots.length > 0 && (
          <SimpleGrid cols={{ base: 1, sm: 2 }} mt="xl">
            {app.screenshots.map(shot => (
              <img
                key={shot.id}
                className={classes.screenshot}
                src={marketImageUrl(app.id, shot.id, 1200)}
                alt={shot.name}
                loading="lazy"
              />
            ))}
          </SimpleGrid>
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
