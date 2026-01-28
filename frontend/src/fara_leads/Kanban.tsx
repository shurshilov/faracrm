import { Kanban } from '@/components/Kanban';
import { Lead } from '@/services/api/lead';
import { FaraRecord } from '@/services/api/crudTypes';

export function ViewKanbanLeads() {
  return (
    <Kanban<Lead>
      model="lead"
      fields={['id', 'name', 'type', 'email', 'phone', 'user_id']}
      groupByField="stage_id"
      groupByModel="lead_stage"
    />
  );
}

export function ViewKanbanLeadStage() {
  return (
    <Kanban<FaraRecord>
      model="lead_stage"
      fields={['id', 'name', 'sequence', 'color']}
    />
  );
}

export function ViewKanbanTeamCrm() {
  return (
    <Kanban<FaraRecord>
      model="team_crm"
      fields={['id', 'name']}
    />
  );
}
