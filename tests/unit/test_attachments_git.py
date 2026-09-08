"""
Unit-тесты git-хранилища вложений
(backend/base/crm/attachments_git/strategies/strategy.py).

Проверяем то, из-за чего скачанный модуль не встанет в проект:
- верхняя папка GitHub («owner-repo-sha») срезается, пути идут от корня;
- папки модуля находятся по имени в любой подпапке репозитория
  (бэкенд — «модуль» с app.py, фронт — «fara_модуль»), соседи не утекают;
- storage_file_id «ref:модули» разбирается;
- шаблон репозитория пропускает только GitHub (сервер ходит туда с
  токеном, произвольный адрес — это SSRF).

No database, no network. Pure function tests.

Run: pytest tests/unit/test_attachments_git.py -v -m unit
"""

import io
import zipfile

import pytest

from backend.base.crm.attachments_git.strategies.strategy import (
    GITHUB_REPO_RE,
    list_modules,
    parse_app_info,
    parse_file_id,
    repack,
)

pytestmark = pytest.mark.unit


def _repo_archive(files: dict[str, bytes]) -> bytes:
    """Архив как у GitHub: всё внутри «owner-repo-sha/»."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("owner-repo-abc123/", "")
        for name, content in files.items():
            zf.writestr(f"owner-repo-abc123/{name}", content)
    return buffer.getvalue()


def _names(archive: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        return sorted(zf.namelist())


class TestFileId:
    def test_ref_and_modules_split_and_strip(self):
        assert parse_file_id("v1.2: leads , telephony ") == (
            "v1.2",
            ["leads", "telephony"],
        )

    def test_empty_ref_means_storage_default(self):
        assert parse_file_id(":leads") == ("", ["leads"])
        assert parse_file_id(None) == ("", [])


class TestRepack:
    FILES = {
        "backend/base/crm/leads/app.py": b"leads",
        "backend/base/crm/leads/models/lead.py": b"model",
        "backend/base/crm/sales/app.py": b"sales",
        "frontend/src/fara_leads/List.tsx": b"list",
        "README.md": b"readme",
    }

    def test_finds_module_folders_by_name_from_repo_root(self):
        result = repack(_repo_archive(self.FILES), ["leads"])

        assert _names(result) == [
            "backend/base/crm/leads/app.py",
            "backend/base/crm/leads/models/lead.py",
            "frontend/src/fara_leads/List.tsx",
        ]

    def test_name_match_is_exact(self):
        """«leads» не должен захватить leads_extra и fara_leads_extra."""
        files = {
            **self.FILES,
            "backend/base/crm/leads_extra/app.py": b"x",
            "frontend/src/fara_leads_extra/List.tsx": b"x",
        }

        result = repack(_repo_archive(files), ["leads"])

        assert not any("leads_extra" in n for n in _names(result))

    def test_folder_without_app_py_is_not_a_module(self):
        """Одноимённая папка без app.py (тесты, документация) — не модуль."""
        files = {**self.FILES, "backend/tests/leads/test_lead.py": b"x"}

        result = repack(_repo_archive(files), ["leads"])

        assert "backend/tests/leads/test_lead.py" not in _names(result)

    def test_module_without_frontend(self):
        """Фронта у модуля может не быть — архив всё равно собирается."""
        result = repack(_repo_archive(self.FILES), ["sales"])

        assert _names(result) == ["backend/base/crm/sales/app.py"]

    def test_several_modules_in_one_archive(self):
        """Фронт с другим именем добавляется вторым модулем: chat_phone,telephony."""
        files = {**self.FILES, "frontend/src/fara_telephony/Calls.tsx": b"x"}

        result = repack(_repo_archive(files), ["sales", "telephony"])

        assert _names(result) == [
            "backend/base/crm/sales/app.py",
            "frontend/src/fara_telephony/Calls.tsx",
        ]

    def test_unknown_module_gives_empty_archive(self):
        assert _names(repack(_repo_archive(self.FILES), ["nope"])) == []


class TestListModules:
    """Импорт каталога: модуль = папка с app.py, где объявлен словарь info."""

    APP = b"""
from backend.base.system.core.app import App


class LeadsApp(App):
    info = {
        "name": "Leads",
        "summary": "Lead management",
        "version": "1.2.0",
        "depends": ["partners"],
    }
"""
    SERVICE = (
        b'class CronApp(App):\n    info = {"name": "Cron", "service": True}\n'
    )

    def test_modules_with_info_in_any_subfolder(self):
        files = {
            "backend/base/crm/leads/app.py": self.APP,
            "backend/base/system/cron/app.py": self.SERVICE,
            "docs/app.py": b"# no info here",
            "backend/base/crm/leads/models/lead.py": b"info = {}",
        }

        modules = list_modules(_repo_archive(files))

        assert set(modules) == {"leads", "cron"}
        assert modules["leads"]["version"] == "1.2.0"
        assert modules["cron"]["service"] is True

    def test_info_with_non_literals_is_still_a_module(self):
        assert parse_app_info(b"info = {'name': NAME}") == {}

    def test_without_info_or_broken_file_is_not_a_module(self):
        assert parse_app_info(b"x = 1") is None
        assert parse_app_info(b"def broken(:") is None


class TestRepoUrl:
    def test_github_repo_forms(self):
        for url in (
            "https://github.com/shurshilov/faracrm",
            "https://github.com/shurshilov/faracrm/",
            "https://github.com/shurshilov/faracrm.git",
        ):
            assert GITHUB_REPO_RE.match(url).groups() == (
                "shurshilov",
                "faracrm",
            )

    def test_other_hosts_and_paths_are_rejected(self):
        for url in (
            "http://github.com/a/b",
            "https://gitlab.com/a/b",
            "https://github.com/a/b/tree/master",
            "https://api.github.com/repos/a/b",
            "",
        ):
            assert GITHUB_REPO_RE.match(url) is None
