"""
Integration tests for Tasks module.

Tests cover:
- Project CRUD
- Task CRUD
- Task stages
- Task tags

Run: pytest tests/integration/tasks/test_tasks.py -v -m integration
"""

import pytest

pytestmark = pytest.mark.integration


class TestProjects:
    """Tests for Project model."""

    async def test_create_project(self):
        from backend.base.crm.tasks.models.project import Project

        pid = await Project.create(Project(name="CRM Development"))
        p = await Project.get(pid)
        assert p.name == "CRM Development"

    async def test_search_projects(self):
        from backend.base.crm.tasks.models.project import Project

        await Project.create(Project(name="Project Alpha"))
        await Project.create(Project(name="Project Beta"))
        projects = await Project.search(fields=["id", "name"])
        assert len(projects) == 2

    async def test_delete_project(self):
        from backend.base.crm.tasks.models.project import Project

        pid = await Project.create(Project(name="To Delete"))
        p = await Project.get(pid)
        await p.delete()
        assert await Project.get(pid) is None


class TestTaskStages:
    """Tests for TaskStage model."""

    async def test_create_task_stage(self):
        from backend.base.crm.tasks.models.task_stage import TaskStage

        sid = await TaskStage.create(TaskStage(name="To Do", sequence=1))
        s = await TaskStage.get(sid)
        assert s.name == "To Do"

    async def test_create_kanban_stages(self):
        from backend.base.crm.tasks.models.task_stage import TaskStage

        stages = [("To Do", 1), ("In Progress", 2), ("Review", 3), ("Done", 4)]
        for name, seq in stages:
            await TaskStage.create(TaskStage(name=name, sequence=seq))
        all_s = await TaskStage.search(
            fields=["id", "name", "sequence"],
            sort="sequence",
            order="asc",
        )
        assert len(all_s) == 4
        assert all_s[0].name == "To Do"
        assert all_s[-1].name == "Done"


class TestTaskTags:
    """Tests for TaskTag model."""

    async def test_create_tag(self):
        from backend.base.crm.tasks.models.task_tag import TaskTag

        tid = await TaskTag.create(TaskTag(name="Bug"))
        t = await TaskTag.get(tid)
        assert t.name == "Bug"

    async def test_multiple_tags(self):
        from backend.base.crm.tasks.models.task_tag import TaskTag

        for name in ["Bug", "Feature", "Improvement", "Documentation"]:
            await TaskTag.create(TaskTag(name=name))
        tags = await TaskTag.search(fields=["id", "name"])
        assert len(tags) == 4


class TestTasks:
    """Tests for Task model."""

    async def test_create_task(self):
        from backend.base.crm.tasks.models.task import Task
        from backend.base.crm.tasks.models.project import Project
        from backend.base.crm.tasks.models.task_stage import TaskStage

        proj_id = await Project.create(Project(name="Test Project"))
        stage_id = await TaskStage.create(TaskStage(name="To Do", sequence=1))

        task_id = await Task.create(
            Task(
                name="Implement feature X",
                project_id=proj_id,
                stage_id=stage_id,
            )
        )
        task = await Task.get(task_id)
        assert task.name == "Implement feature X"

    async def test_search_tasks_by_project(self):
        from backend.base.crm.tasks.models.task import Task
        from backend.base.crm.tasks.models.project import Project
        from backend.base.crm.tasks.models.task_stage import TaskStage

        p1 = await Project.create(Project(name="Project A"))
        p2 = await Project.create(Project(name="Project B"))
        sid = await TaskStage.create(TaskStage(name="To Do", sequence=1))

        await Task.create(Task(name="Task A1", project_id=p1, stage_id=sid))
        await Task.create(Task(name="Task A2", project_id=p1, stage_id=sid))
        await Task.create(Task(name="Task B1", project_id=p2, stage_id=sid))

        a_tasks = await Task.search(
            fields=["id", "name"],
            filter=[("project_id", "=", p1)],
        )
        assert len(a_tasks) == 2

    async def test_move_task_stage(self):
        from backend.base.crm.tasks.models.task import Task
        from backend.base.crm.tasks.models.project import Project
        from backend.base.crm.tasks.models.task_stage import TaskStage

        proj = await Project.create(Project(name="Project"))
        s1 = await TaskStage.create(TaskStage(name="To Do", sequence=1))
        s2 = await TaskStage.create(TaskStage(name="Done", sequence=2))

        task_id = await Task.create(
            Task(name="Move Me", project_id=proj, stage_id=s1)
        )
        task = await Task.get(task_id)
        await task.update(Task(stage_id=s2))

        updated = await Task.get(task_id, fields=["id", "stage_id"])
        assert updated.stage_id.id == s2

    async def test_delete_task(self):
        from backend.base.crm.tasks.models.task import Task
        from backend.base.crm.tasks.models.project import Project
        from backend.base.crm.tasks.models.task_stage import TaskStage

        proj = await Project.create(Project(name="Project"))
        sid = await TaskStage.create(TaskStage(name="To Do", sequence=1))
        task_id = await Task.create(
            Task(name="Delete", project_id=proj, stage_id=sid)
        )
        task = await Task.get(task_id)
        await task.delete()
        assert await Task.get(task_id) is None
