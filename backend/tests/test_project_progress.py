import unittest

from sqlalchemy import (
    Column, Integer, MetaData, String, Table, create_engine, delete, func, select, update,
)

from app.repositories.project_progress import project_progress_rows


class ProjectProgressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        metadata = MetaData()
        # 只为查询建立隔离样本表，不修改生产 Models 或 MySQL 结构。
        self.projects = Table(
            "projects", metadata,
            Column("id", Integer, primary_key=True),
            Column("owner_id", Integer),
            Column("progress", Integer),
        )
        self.tasks = Table(
            "daily_tasks", metadata,
            Column("id", Integer, primary_key=True),
            Column("project_id", Integer),
            Column("user_id", Integer),
            Column("status", String),
        )
        metadata.create_all(self.engine)
        self.connection = self.engine.connect()

    def tearDown(self) -> None:
        self.connection.close()
        self.engine.dispose()

    def add_project(self, project_id: int, owner_id: int = 1, progress: int = 0) -> None:
        self.connection.execute(self.projects.insert().values(
            id=project_id, owner_id=owner_id, progress=progress,
        ))

    def add_tasks(self, project_id: int, completed: int, total: int, user_id: int = 1) -> None:
        self.connection.execute(self.tasks.insert(), [
            {"project_id": project_id, "user_id": user_id,
             "status": "completed" if index < completed else "pending"}
            for index in range(total)
        ])

    def progress(self, project_id: int) -> int:
        rows = project_progress_rows()
        return int(self.connection.scalar(
            select(rows.c.progress).where(rows.c.project_id == project_id)
        ))

    def test_empty_projects_and_no_tasks_preserve_fallback(self) -> None:
        rows = project_progress_rows()
        self.assertIsNone(self.connection.scalar(select(func.avg(rows.c.progress))))
        self.add_project(1, progress=40)
        self.assertEqual(self.progress(1), 40)

    def test_only_owner_tasks_contribute_and_owner_average_is_isolated(self) -> None:
        self.add_project(1)
        self.add_project(2, owner_id=2, progress=70)
        self.add_tasks(1, 1, 2)
        self.add_tasks(1, 0, 8, user_id=2)
        self.assertEqual(self.progress(1), 50)
        rows = project_progress_rows()
        self.assertEqual(self.connection.scalar(
            select(func.avg(rows.c.progress)).where(rows.c.owner_id == 2)
        ), 70)
        self.assertEqual(self.connection.scalar(select(func.avg(rows.c.progress))), 60)

    def test_rounding_matches_workspace_including_half_to_even(self) -> None:
        for project_id, (completed, total) in enumerate(
            ((0, 1), (1, 1), (1, 3), (2, 3), (1, 8), (3, 8), (7, 8)), start=1,
        ):
            with self.subTest(completed=completed, total=total):
                self.add_project(project_id)
                self.add_tasks(project_id, completed, total)
                self.assertEqual(self.progress(project_id), round(completed * 100 / total))

    def test_complete_reopen_and_delete_are_reflected_without_stored_progress_writes(self) -> None:
        self.add_project(1, progress=20)
        self.add_tasks(1, 0, 1)
        self.assertEqual(self.progress(1), 0)
        self.connection.execute(update(self.tasks).values(status="completed"))
        self.assertEqual(self.progress(1), 100)
        self.connection.execute(update(self.tasks).values(status="pending"))
        self.assertEqual(self.progress(1), 0)
        self.connection.execute(delete(self.tasks))
        self.assertEqual(self.progress(1), 20)
        self.assertEqual(self.connection.scalar(select(self.projects.c.progress)), 20)


if __name__ == "__main__":
    unittest.main()
