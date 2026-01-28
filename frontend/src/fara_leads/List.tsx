import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { Lead } from '@/services/api/lead';

// Простой тип для TeamCrm
export type TeamCrm = {
  id: number;
  name: string;
};

export function ViewListLeads() {
  return (
    <List<Lead> model="lead" order="desc" sort="id">
      <Field name="id" />
      <Field name="name" />
      <Field name="type" />
      <Field name="email" />
      <Field name="phone" />
      <Field name="user_id" />
      <Field name="parent_id" />
      <Field name="company_id" />
      <Field name="stage_id" />
      <Field name="active" />
    </List>
  );
}

export function ViewListTeamCrm() {
  return (
    <List<TeamCrm> model="team_crm" order="desc" sort="id">
      <Field name="id" />
      <Field name="name" />
    </List>
  );
}

export function ViewListLeadStage() {
  return (
    <List<FaraRecord> model="lead_stage" order="asc" sort="sequence">
      <Field name="id" />
      <Field name="name" />
      <Field name="sequence" />
      <Field name="color" />
      <Field name="fold" />
    </List>
  );
}
