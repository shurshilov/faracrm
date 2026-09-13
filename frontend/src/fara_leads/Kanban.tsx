import { Kanban } from '@/components/Kanban';
import type {
  LeadRecord,
  LeadStageRecord,
  TeamCrmRecord,
} from '@/types/records';

export function ViewKanbanLeads() {
  // Содержимое карточки (прогресс, партнёр, ответственный, дата создания) —
  // расширение extensions/KanbanCardLead; здесь только заголовок и стадии.
  return (
    <Kanban<LeadRecord>
      model="leads"
      groupByField="stage_id"
      groupByModel="lead_stage"
      groupByFilter={[['active', '=', true]]}
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
