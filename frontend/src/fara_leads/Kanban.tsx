import { Kanban } from '@/components/Kanban';
import type {
  LeadRecord,
  LeadStageRecord,
  TeamCrmRecord,
} from '@/types/records';

export function ViewKanbanLeads() {
  return (
    <Kanban<LeadRecord>
      model="leads"
      fields={['id', 'name', 'type', 'email', 'phone', 'user_id']}
      groupByField="stage_id"
      groupByModel="lead_stage"
    />
  );
}

export function ViewKanbanLeadStage() {
  return (
    <Kanban<LeadStageRecord>
      model="lead_stage"
      fields={['id', 'name', 'sequence', 'color']}
    />
  );
}

export function ViewKanbanTeamCrm() {
  return <Kanban<TeamCrmRecord> model="team_crm" fields={['id', 'name']} />;
}
