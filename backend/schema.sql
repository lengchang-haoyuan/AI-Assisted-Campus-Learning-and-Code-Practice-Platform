-- ScholarHub P01 initial schema for MySQL 8.0+
-- Storage convention: all DATETIME(6) values are UTC. API datetimes include an offset.
-- This script is intentionally non-destructive and is intended for an empty database.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;
SET time_zone = '+00:00';

CREATE DATABASE IF NOT EXISTS scholarhub
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE scholarhub;

CREATE TABLE users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    avatar_url VARCHAR(500) NULL,
    bio TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email UNIQUE (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE projects (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    owner_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(120) NOT NULL,
    description TEXT NULL,
    difficulty VARCHAR(16) NOT NULL DEFAULT 'beginner',
    status VARCHAR(20) NOT NULL DEFAULT 'not_started',
    language VARCHAR(100) NULL,
    framework VARCHAR(100) NULL,
    frontend VARCHAR(100) NULL,
    backend VARCHAR(100) NULL,
    `database` VARCHAR(100) NULL,
    requirements JSON NULL,
    output_requirement TEXT NULL,
    context_data JSON NULL,
    cover_url VARCHAR(500) NULL,
    repository_url VARCHAR(500) NULL,
    result_summary TEXT NULL,
    progress SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    published_at DATETIME(6) NULL,
    completed_at DATETIME(6) NULL,
    view_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_projects PRIMARY KEY (id),
    CONSTRAINT fk_projects_owner_id_users FOREIGN KEY (owner_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_projects_project_difficulty CHECK (
        difficulty IN ('beginner', 'intermediate', 'advanced')
    ),
    CONSTRAINT ck_projects_project_status CHECK (
        status IN ('not_started', 'in_progress', 'completed', 'published', 'archived')
    ),
    CONSTRAINT ck_projects_progress_range CHECK (progress BETWEEN 0 AND 100),
    INDEX ix_projects_owner_status (owner_id, status),
    INDEX ix_projects_published_created (is_published, created_at),
    INDEX ix_projects_created_at (created_at),
    INDEX ix_projects_completed_at (completed_at),
    INDEX ix_projects_published_at (published_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE tags (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    slug VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_tags PRIMARY KEY (id),
    CONSTRAINT uq_tags_name UNIQUE (name),
    CONSTRAINT uq_tags_slug UNIQUE (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE project_tags (
    project_id BIGINT UNSIGNED NOT NULL,
    tag_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_project_tags PRIMARY KEY (project_id, tag_id),
    CONSTRAINT fk_project_tags_project_id_projects FOREIGN KEY (project_id)
        REFERENCES projects (id) ON DELETE CASCADE,
    CONSTRAINT fk_project_tags_tag_id_tags FOREIGN KEY (tag_id)
        REFERENCES tags (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE comments (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    project_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    content TEXT NOT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_comments PRIMARY KEY (id),
    CONSTRAINT fk_comments_project_id_projects FOREIGN KEY (project_id)
        REFERENCES projects (id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_user_id_users FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    INDEX ix_comments_project_created (project_id, created_at),
    INDEX ix_comments_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE likes (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    project_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_likes PRIMARY KEY (id),
    CONSTRAINT uq_likes_user_project UNIQUE (user_id, project_id),
    CONSTRAINT fk_likes_user_id_users FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_likes_project_id_projects FOREIGN KEY (project_id)
        REFERENCES projects (id) ON DELETE CASCADE,
    INDEX ix_likes_project_created (project_id, created_at),
    INDEX ix_likes_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE favorites (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    project_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_favorites PRIMARY KEY (id),
    CONSTRAINT uq_favorites_user_project UNIQUE (user_id, project_id),
    CONSTRAINT fk_favorites_user_id_users FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_favorites_project_id_projects FOREIGN KEY (project_id)
        REFERENCES projects (id) ON DELETE CASCADE,
    INDEX ix_favorites_project_created (project_id, created_at),
    INDEX ix_favorites_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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

CREATE TABLE courses (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    owner_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(120) NOT NULL,
    code VARCHAR(50) NULL,
    description TEXT NULL,
    instructor VARCHAR(100) NULL,
    schedule_data JSON NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_courses PRIMARY KEY (id),
    CONSTRAINT uq_courses_owner_name UNIQUE (owner_id, name),
    CONSTRAINT fk_courses_owner_id_users FOREIGN KEY (owner_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_courses_course_status CHECK (
        status IN ('active', 'completed', 'archived')
    ),
    INDEX ix_courses_owner_status (owner_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE learning_plans (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    project_id BIGINT UNSIGNED NULL,
    course_id BIGINT UNSIGNED NULL,
    title VARCHAR(160) NOT NULL,
    description TEXT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'draft',
    start_date DATE NULL,
    end_date DATE NULL,
    goal_data JSON NULL,
    progress SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_learning_plans PRIMARY KEY (id),
    CONSTRAINT fk_learning_plans_user_id_users FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_learning_plans_project_id_projects FOREIGN KEY (project_id)
        REFERENCES projects (id) ON DELETE SET NULL,
    CONSTRAINT fk_learning_plans_course_id_courses FOREIGN KEY (course_id)
        REFERENCES courses (id) ON DELETE SET NULL,
    CONSTRAINT ck_learning_plans_learning_plan_status CHECK (
        status IN ('draft', 'active', 'completed', 'cancelled')
    ),
    CONSTRAINT ck_learning_plans_valid_date_range CHECK (
        end_date IS NULL OR start_date IS NULL OR end_date >= start_date
    ),
    CONSTRAINT ck_learning_plans_progress_range CHECK (progress BETWEEN 0 AND 100),
    INDEX ix_learning_plans_user_status (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE daily_tasks (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    plan_id BIGINT UNSIGNED NULL,
    project_id BIGINT UNSIGNED NULL,
    title VARCHAR(160) NOT NULL,
    description TEXT NULL,
    priority VARCHAR(8) NOT NULL DEFAULT 'medium',
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    scheduled_date DATE NOT NULL,
    start_time TIME NULL,
    end_time TIME NULL,
    estimated_minutes INTEGER UNSIGNED NULL,
    completed_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_daily_tasks PRIMARY KEY (id),
    CONSTRAINT fk_daily_tasks_user_id_users FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_daily_tasks_plan_id_learning_plans FOREIGN KEY (plan_id)
        REFERENCES learning_plans (id) ON DELETE SET NULL,
    CONSTRAINT fk_daily_tasks_project_id_projects FOREIGN KEY (project_id)
        REFERENCES projects (id) ON DELETE SET NULL,
    CONSTRAINT ck_daily_tasks_task_priority CHECK (
        priority IN ('low', 'medium', 'high')
    ),
    CONSTRAINT ck_daily_tasks_task_status CHECK (
        status IN ('pending', 'in_progress', 'completed', 'cancelled')
    ),
    CONSTRAINT ck_daily_tasks_estimated_minutes_nonnegative CHECK (
        estimated_minutes IS NULL OR estimated_minutes >= 0
    ),
    CONSTRAINT ck_daily_tasks_valid_time_range CHECK (
        end_time IS NULL OR start_time IS NULL OR end_time > start_time
    ),
    INDEX ix_daily_tasks_user_schedule (user_id, scheduled_date, status),
    INDEX ix_daily_tasks_plan_status (plan_id, status),
    INDEX ix_daily_tasks_completed_at (completed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE workflows (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    project_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(120) NOT NULL,
    description TEXT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'draft',
    version INTEGER UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_workflows PRIMARY KEY (id),
    CONSTRAINT uq_workflows_project_name UNIQUE (project_id, name),
    CONSTRAINT fk_workflows_project_id_projects FOREIGN KEY (project_id)
        REFERENCES projects (id) ON DELETE CASCADE,
    CONSTRAINT ck_workflows_workflow_status CHECK (
        status IN ('draft', 'ready', 'running', 'completed', 'failed', 'stale')
    ),
    CONSTRAINT ck_workflows_version_positive CHECK (version >= 1),
    INDEX ix_workflows_project_status (project_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE workflow_nodes (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    workflow_id BIGINT UNSIGNED NOT NULL,
    node_key VARCHAR(64) NOT NULL,
    node_type VARCHAR(50) NOT NULL,
    name VARCHAR(120) NOT NULL,
    position_x NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    position_y NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    config JSON NULL,
    input_data JSON NULL,
    output_data JSON NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    context_version INTEGER UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_workflow_nodes PRIMARY KEY (id),
    CONSTRAINT uq_nodes_workflow_key UNIQUE (workflow_id, node_key),
    CONSTRAINT uq_nodes_id_workflow UNIQUE (id, workflow_id),
    CONSTRAINT fk_workflow_nodes_workflow_id_workflows FOREIGN KEY (workflow_id)
        REFERENCES workflows (id) ON DELETE CASCADE,
    CONSTRAINT ck_workflow_nodes_workflow_node_status CHECK (
        status IN ('pending', 'running', 'success', 'failed', 'stale')
    ),
    CONSTRAINT ck_workflow_nodes_context_version_positive CHECK (context_version >= 1),
    INDEX ix_workflow_nodes_workflow_status (workflow_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE workflow_edges (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    workflow_id BIGINT UNSIGNED NOT NULL,
    source_node_id BIGINT UNSIGNED NOT NULL,
    target_node_id BIGINT UNSIGNED NOT NULL,
    condition_data JSON NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_workflow_edges PRIMARY KEY (id),
    CONSTRAINT uq_edges_workflow_nodes UNIQUE (
        workflow_id, source_node_id, target_node_id
    ),
    CONSTRAINT fk_workflow_edges_workflow_id_workflows FOREIGN KEY (workflow_id)
        REFERENCES workflows (id) ON DELETE CASCADE,
    CONSTRAINT fk_edges_source_node_workflow FOREIGN KEY (source_node_id, workflow_id)
        REFERENCES workflow_nodes (id, workflow_id) ON DELETE CASCADE,
    CONSTRAINT fk_edges_target_node_workflow FOREIGN KEY (target_node_id, workflow_id)
        REFERENCES workflow_nodes (id, workflow_id) ON DELETE CASCADE,
    CONSTRAINT ck_workflow_edges_different_nodes CHECK (
        source_node_id <> target_node_id
    ),
    INDEX ix_workflow_edges_target (workflow_id, target_node_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE workflow_runs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    workflow_id BIGINT UNSIGNED NOT NULL,
    started_by_id BIGINT UNSIGNED NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    context_snapshot JSON NULL,
    error_code VARCHAR(64) NULL,
    error_message VARCHAR(1000) NULL,
    started_at DATETIME(6) NULL,
    finished_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_workflow_runs PRIMARY KEY (id),
    CONSTRAINT fk_workflow_runs_workflow_id_workflows FOREIGN KEY (workflow_id)
        REFERENCES workflows (id) ON DELETE CASCADE,
    CONSTRAINT fk_workflow_runs_started_by_id_users FOREIGN KEY (started_by_id)
        REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT ck_workflow_runs_workflow_run_status CHECK (
        status IN ('pending', 'running', 'completed', 'failed', 'cancelled')
    ),
    INDEX ix_workflow_runs_workflow_created (workflow_id, created_at),
    INDEX ix_workflow_runs_started_by_status (started_by_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE ai_requests (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    project_id BIGINT UNSIGNED NULL,
    workflow_run_id BIGINT UNSIGNED NULL,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    request_type VARCHAR(50) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    input_hash VARCHAR(64) NOT NULL,
    input_summary VARCHAR(500) NULL,
    request_metadata JSON NULL,
    prompt_tokens INTEGER UNSIGNED NULL,
    completion_tokens INTEGER UNSIGNED NULL,
    latency_ms INTEGER UNSIGNED NULL,
    error_code VARCHAR(64) NULL,
    error_message VARCHAR(1000) NULL,
    requested_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    finished_at DATETIME(6) NULL,
    CONSTRAINT pk_ai_requests PRIMARY KEY (id),
    CONSTRAINT fk_ai_requests_user_id_users FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_ai_requests_project_id_projects FOREIGN KEY (project_id)
        REFERENCES projects (id) ON DELETE SET NULL,
    CONSTRAINT fk_ai_requests_workflow_run_id_workflow_runs FOREIGN KEY (workflow_run_id)
        REFERENCES workflow_runs (id) ON DELETE SET NULL,
    CONSTRAINT ck_ai_requests_ai_request_status CHECK (
        status IN ('pending', 'running', 'completed', 'failed')
    ),
    CONSTRAINT ck_ai_requests_prompt_tokens_nonnegative CHECK (
        prompt_tokens IS NULL OR prompt_tokens >= 0
    ),
    CONSTRAINT ck_ai_requests_completion_tokens_nonnegative CHECK (
        completion_tokens IS NULL OR completion_tokens >= 0
    ),
    CONSTRAINT ck_ai_requests_latency_nonnegative CHECK (
        latency_ms IS NULL OR latency_ms >= 0
    ),
    INDEX ix_ai_requests_user_requested (user_id, requested_at),
    INDEX ix_ai_requests_project_status (project_id, status),
    INDEX ix_ai_requests_workflow_run (workflow_run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE ai_results (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    request_id BIGINT UNSIGNED NOT NULL,
    result_type VARCHAR(50) NOT NULL,
    structured_result JSON NULL,
    text_summary TEXT NULL,
    content_hash VARCHAR(64) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_ai_results PRIMARY KEY (id),
    CONSTRAINT uq_ai_results_request_id UNIQUE (request_id),
    CONSTRAINT fk_ai_results_request_id_ai_requests FOREIGN KEY (request_id)
        REFERENCES ai_requests (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE learning_records (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    project_id BIGINT UNSIGNED NULL,
    course_id BIGINT UNSIGNED NULL,
    task_id BIGINT UNSIGNED NULL,
    record_type VARCHAR(16) NOT NULL,
    title VARCHAR(160) NOT NULL,
    content TEXT NULL,
    duration_minutes INTEGER UNSIGNED NULL,
    occurred_at DATETIME(6) NOT NULL,
    record_metadata JSON NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_learning_records PRIMARY KEY (id),
    CONSTRAINT fk_learning_records_user_id_users FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_learning_records_project_id_projects FOREIGN KEY (project_id)
        REFERENCES projects (id) ON DELETE SET NULL,
    CONSTRAINT fk_learning_records_course_id_courses FOREIGN KEY (course_id)
        REFERENCES courses (id) ON DELETE SET NULL,
    CONSTRAINT fk_learning_records_task_id_daily_tasks FOREIGN KEY (task_id)
        REFERENCES daily_tasks (id) ON DELETE SET NULL,
    CONSTRAINT ck_learning_records_record_type CHECK (
        record_type IN ('study', 'project', 'workflow', 'ai', 'course', 'task')
    ),
    CONSTRAINT ck_learning_records_duration_nonnegative CHECK (
        duration_minutes IS NULL OR duration_minutes >= 0
    ),
    INDEX ix_learning_records_user_occurred (user_id, occurred_at),
    INDEX ix_learning_records_project_type (project_id, record_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE learning_reports (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    ai_result_id BIGINT UNSIGNED NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    summary TEXT NULL,
    achievements JSON NULL,
    problems JSON NULL,
    suggestions JSON NULL,
    structured_data JSON NULL,
    generated_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_learning_reports PRIMARY KEY (id),
    CONSTRAINT uq_reports_user_period UNIQUE (user_id, period_start, period_end),
    CONSTRAINT uq_learning_reports_ai_result_id UNIQUE (ai_result_id),
    CONSTRAINT fk_learning_reports_user_id_users FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_learning_reports_ai_result_id_ai_results FOREIGN KEY (ai_result_id)
        REFERENCES ai_results (id) ON DELETE SET NULL,
    CONSTRAINT ck_learning_reports_report_status CHECK (
        status IN ('pending', 'completed', 'failed')
    ),
    CONSTRAINT ck_learning_reports_valid_period CHECK (period_end >= period_start),
    INDEX ix_learning_reports_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
