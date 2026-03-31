import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import RelationCell from '@/components/ListCells/RelationCell';

import type {
  LeadRecord,
  LeadStageRecord,
  TeamCrmRecord,
} from '@/types/records';
import { useTranslation } from 'react-i18next';

export function ViewListLeads() {
  const { t } = useTranslation('leads');
  return (
    <List<LeadRecord> model="leads" order="desc" sort="id">
      <Field name="id" label={t('leads.id')} />
      <Field name="name" label={t('leads.name')} />
      <Field name="type" label={t('leads.type')} />
      <Field
        name="user_id"
        label={t('leads.user_id')}
        render={value => <RelationCell value={value} model="users" />}
      />
      <Field
        name="parent_id"
        label={t('leads.parent_id')}
        render={value => <RelationCell value={value} model="partners" />}
      />
      <Field
        name="company_id"
        label={t('leads.company_id')}
        render={value => <RelationCell value={value} model="company" />}
      />
      <Field
        name="stage_id"
        label={t('leads.stage_id')}
        render={value => <RelationCell value={value} model="stages" />}
      />
      <Field name="active" label={t('leads.active')} />
    </List>
  );
}

export function ViewListTeamCrm() {
  const { t } = useTranslation('leads');
  return (
    <List<TeamCrmRecord> model="team_crm" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
    </List>
  );
}

export function ViewListLeadStage() {
  const { t } = useTranslation('leads');
  return (
    <List<LeadStageRecord> model="lead_stage" order="asc" sort="sequence">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="sequence" label={t('fields.sequence')} />
      <Field name="color" label={t('fields.color')} />
      <Field name="fold" label={t('fields.fold')} />
    </List>
  );
}
