/**
 * Где студия ставит зону «Дополнительно» относительно разметки формы
 * (form_settings.extra_placement):
 *   bottom — под разметкой;
 *   side   — колонкой справа (на узкой форме — под разметкой);
 *   tab    — последней вкладкой FormTabs формы (FormTabsExtraContext ядра).
 */
import { ReactNode, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { IconListDetails } from '@tabler/icons-react';
import { FormTabsExtraContext } from '@/components/Form/Layout/FormTabs';
import type { ExtraPlacement } from './zoneGrid';
import classes from './ExtraZone.module.css';

interface ZoneLayoutProps {
  placement: ExtraPlacement;
  zone: ReactNode;
  /** Разметка формы. */
  children: ReactNode;
}

function SideLayout({ zone, children }: Omit<ZoneLayoutProps, 'placement'>) {
  return (
    <div className={classes.sideContainer}>
      <div className={classes.sideLayout}>
        <div className={classes.main}>{children}</div>
        {zone}
      </div>
    </div>
  );
}

export function ZoneLayout({ placement, zone, children }: ZoneLayoutProps) {
  const { t } = useTranslation('studio');
  const tabs = useMemo(
    () => [
      {
        name: 'extra_fields',
        label: t('zone.title'),
        icon: <IconListDetails size={16} />,
        children: zone,
      },
    ],
    [t, zone],
  );

  if (placement === 'side') {
    return <SideLayout zone={zone}>{children}</SideLayout>;
  }
  if (placement === 'tab') {
    return (
      <FormTabsExtraContext.Provider value={tabs}>
        {children}
      </FormTabsExtraContext.Provider>
    );
  }
  return (
    <>
      {children}
      {zone}
    </>
  );
}
