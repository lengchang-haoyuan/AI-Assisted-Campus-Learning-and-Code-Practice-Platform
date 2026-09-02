-- ScholarHub P14 statistics migration for an existing P01-P13 database.
-- Preconditions: run once against a schema that matches commit 725b2cb.
-- This migration is additive and does not backfill unverifiable historical events.
-- DATETIME(6) values are stored in UTC.

SET time_zone = '+00:00';

ALTER TABLE projects
    ADD COLUMN completed_at DATETIME(6) NULL AFTER published_at,
    ADD INDEX ix_projects_created_at (created_at),
    ADD INDEX ix_projects_completed_at (completed_at),
    ADD INDEX ix_projects_published_at (published_at);

ALTER TABLE comments
    ADD INDEX ix_comments_created_at (created_at);

ALTER TABLE likes
    ADD INDEX ix_likes_created_at (created_at);

ALTER TABLE favorites
    ADD INDEX ix_favorites_created_at (created_at);

ALTER TABLE daily_tasks
    ADD INDEX ix_daily_tasks_completed_at (completed_at);

CREATE TABLE project_views (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    project_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    viewed_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_project_views PRIMARY KEY (id),
    CONSTRAINT fk_project_views_project_id_projects FOREIGN KEY (project_id)
        REFERENCES projects (id) ON DELETE CASCADE,
    CONSTRAINT fk_project_views_user_id_users FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    INDEX ix_project_views_viewed_user (viewed_at, user_id),
    INDEX ix_project_views_project_viewed (project_id, viewed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
