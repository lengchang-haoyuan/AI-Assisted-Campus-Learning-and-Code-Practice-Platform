ALTER TABLE comments
    ADD COLUMN moderation_status VARCHAR(16) NOT NULL DEFAULT 'visible' AFTER deleted_at,
    ADD COLUMN moderated_at DATETIME(6) NULL AFTER moderation_status,
    ADD COLUMN revision INT NOT NULL DEFAULT 1 AFTER moderated_at,
    ADD CONSTRAINT ck_comments_comment_moderation_status CHECK (
        moderation_status IN ('visible', 'hidden')
    ),
    ADD INDEX ix_comments_project_moderation_created (
        project_id, moderation_status, created_at, id
    );

CREATE TABLE community_publications (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    project_id BIGINT UNSIGNED NULL,
    owner_user_id BIGINT UNSIGNED NOT NULL,
    kind VARCHAR(24) NOT NULL DEFAULT 'work',
    status VARCHAR(24) NOT NULL,
    public_version_number INT NULL,
    pending_version_number INT NULL,
    revision INT NOT NULL DEFAULT 1,
    submitted_at DATETIME(6) NULL,
    reviewed_at DATETIME(6) NULL,
    published_at DATETIME(6) NULL,
    withdrawn_at DATETIME(6) NULL,
    taken_down_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_community_publications PRIMARY KEY (id),
    CONSTRAINT uq_community_publications_project_id UNIQUE (project_id),
    CONSTRAINT fk_publication_project FOREIGN KEY (project_id)
        REFERENCES projects (id) ON DELETE SET NULL,
    CONSTRAINT fk_publication_owner FOREIGN KEY (owner_user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_community_publications_community_publication_kind CHECK (
        kind IN ('work', 'practice_template')
    ),
    CONSTRAINT ck_community_publications_community_publication_status CHECK (
        status IN (
            'legacy_review_required', 'pending_review', 'approved',
            'returned', 'withdrawn', 'taken_down'
        )
    ),
    INDEX ix_publication_status_submitted (status, submitted_at, id),
    INDEX ix_publication_owner_updated (owner_user_id, updated_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE community_publication_versions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    publication_id BIGINT UNSIGNED NOT NULL,
    version_number INT NOT NULL,
    request_key VARCHAR(64) NOT NULL,
    project_updated_at DATETIME(6) NOT NULL,
    kind VARCHAR(24) NOT NULL,
    name VARCHAR(120) NOT NULL,
    description TEXT NULL,
    difficulty VARCHAR(16) NOT NULL,
    project_status VARCHAR(20) NOT NULL,
    language VARCHAR(100) NULL,
    framework VARCHAR(100) NULL,
    frontend VARCHAR(100) NULL,
    backend VARCHAR(100) NULL,
    `database` VARCHAR(100) NULL,
    repository_url VARCHAR(500) NULL,
    tag_names JSON NOT NULL,
    attribution VARCHAR(160) NULL,
    source_license_statement VARCHAR(500) NULL,
    ai_assistance_statement VARCHAR(1000) NULL,
    human_review_statement VARCHAR(1000) NULL,
    submitted_at DATETIME(6) NOT NULL,
    CONSTRAINT pk_community_publication_versions PRIMARY KEY (id),
    CONSTRAINT uq_publication_version UNIQUE (publication_id, version_number),
    CONSTRAINT uq_publication_request UNIQUE (publication_id, request_key),
    CONSTRAINT fk_publication_version_publication FOREIGN KEY (publication_id)
        REFERENCES community_publications (id) ON DELETE RESTRICT,
    CONSTRAINT ck_community_publication_versions_positive_version CHECK (
        version_number >= 1
    ),
    CONSTRAINT ck_community_publication_versions_publication_version_kind CHECK (
        kind IN ('work', 'practice_template')
    ),
    CONSTRAINT ck_community_publication_versions_publication_project_difficulty CHECK (
        difficulty IN ('beginner', 'intermediate', 'advanced')
    ),
    CONSTRAINT ck_community_publication_versions_publication_project_status CHECK (
        project_status IN ('not_started', 'in_progress', 'completed', 'published', 'archived')
    ),
    INDEX ix_publication_version_submitted (submitted_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE community_publications
    ADD CONSTRAINT fk_publication_public_version
        FOREIGN KEY (id, public_version_number)
        REFERENCES community_publication_versions (publication_id, version_number)
        ON DELETE RESTRICT,
    ADD CONSTRAINT fk_publication_pending_version
        FOREIGN KEY (id, pending_version_number)
        REFERENCES community_publication_versions (publication_id, version_number)
        ON DELETE RESTRICT;

CREATE TABLE community_governance_actions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    actor_user_id BIGINT UNSIGNED NOT NULL,
    target_owner_user_id BIGINT UNSIGNED NOT NULL,
    publication_id BIGINT UNSIGNED NULL,
    publication_version_number INT NULL,
    comment_id BIGINT UNSIGNED NULL,
    action VARCHAR(24) NOT NULL,
    from_status VARCHAR(32) NULL,
    to_status VARCHAR(32) NOT NULL,
    reason VARCHAR(500) NOT NULL,
    target_excerpt TEXT NOT NULL,
    occurred_at DATETIME(6) NOT NULL,
    CONSTRAINT pk_community_governance_actions PRIMARY KEY (id),
    CONSTRAINT fk_governance_action_actor FOREIGN KEY (actor_user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_governance_action_owner FOREIGN KEY (target_owner_user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_governance_action_version
        FOREIGN KEY (publication_id, publication_version_number)
        REFERENCES community_publication_versions (publication_id, version_number)
        ON DELETE RESTRICT,
    CONSTRAINT fk_governance_action_comment FOREIGN KEY (comment_id)
        REFERENCES comments (id) ON DELETE RESTRICT,
    CONSTRAINT ck_community_governance_actions_single_target CHECK (
        (publication_id IS NOT NULL AND publication_version_number IS NOT NULL AND comment_id IS NULL)
        OR (publication_id IS NULL AND publication_version_number IS NULL AND comment_id IS NOT NULL)
    ),
    CONSTRAINT ck_community_governance_actions_community_governance_action CHECK (
        action IN (
            'apply', 'approve', 'return', 'withdraw', 'take_down',
            'restore', 'hide_comment', 'restore_comment'
        )
    ),
    INDEX ix_governance_action_publication_time (publication_id, occurred_at, id),
    INDEX ix_governance_action_comment_time (comment_id, occurred_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE community_governance_cases (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    case_type VARCHAR(16) NOT NULL,
    opened_by_user_id BIGINT UNSIGNED NOT NULL,
    target_owner_user_id BIGINT UNSIGNED NOT NULL,
    request_key VARCHAR(64) NOT NULL,
    publication_id BIGINT UNSIGNED NULL,
    publication_version_number INT NULL,
    comment_id BIGINT UNSIGNED NULL,
    target_action_id BIGINT UNSIGNED NULL,
    reason VARCHAR(500) NOT NULL,
    target_excerpt TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    resolution_reason VARCHAR(500) NULL,
    reviewed_by_user_id BIGINT UNSIGNED NULL,
    resolved_action_id BIGINT UNSIGNED NULL,
    resolved_at DATETIME(6) NULL,
    revision INT NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_community_governance_cases PRIMARY KEY (id),
    CONSTRAINT uq_governance_case_publication UNIQUE (
        opened_by_user_id, case_type, publication_id, publication_version_number
    ),
    CONSTRAINT uq_governance_case_comment UNIQUE (
        opened_by_user_id, case_type, comment_id
    ),
    CONSTRAINT uq_governance_case_action UNIQUE (
        opened_by_user_id, case_type, target_action_id
    ),
    CONSTRAINT uq_governance_case_request UNIQUE (opened_by_user_id, request_key),
    CONSTRAINT fk_governance_case_opener FOREIGN KEY (opened_by_user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_governance_case_owner FOREIGN KEY (target_owner_user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_governance_case_version
        FOREIGN KEY (publication_id, publication_version_number)
        REFERENCES community_publication_versions (publication_id, version_number)
        ON DELETE RESTRICT,
    CONSTRAINT fk_governance_case_comment FOREIGN KEY (comment_id)
        REFERENCES comments (id) ON DELETE RESTRICT,
    CONSTRAINT fk_governance_case_target_action FOREIGN KEY (target_action_id)
        REFERENCES community_governance_actions (id) ON DELETE RESTRICT,
    CONSTRAINT fk_governance_case_reviewer FOREIGN KEY (reviewed_by_user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_governance_case_result_action FOREIGN KEY (resolved_action_id)
        REFERENCES community_governance_actions (id) ON DELETE RESTRICT,
    CONSTRAINT ck_community_governance_cases_case_target CHECK (
        (case_type = 'report' AND target_action_id IS NULL AND (
            (publication_id IS NOT NULL AND publication_version_number IS NOT NULL AND comment_id IS NULL)
            OR (publication_id IS NULL AND publication_version_number IS NULL AND comment_id IS NOT NULL)
        ))
        OR (case_type = 'appeal' AND publication_id IS NULL
            AND publication_version_number IS NULL AND comment_id IS NULL
            AND target_action_id IS NOT NULL)
    ),
    CONSTRAINT ck_community_governance_cases_community_governance_case_type CHECK (
        case_type IN ('report', 'appeal')
    ),
    CONSTRAINT ck_community_governance_cases_community_governance_case_status CHECK (
        status IN ('pending', 'accepted', 'rejected')
    ),
    INDEX ix_governance_case_status_created (status, created_at, id),
    INDEX ix_governance_case_owner_created (opened_by_user_id, created_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE notifications
    DROP CHECK ck_notifications_notification_kind,
    MODIFY COLUMN assignment_id BIGINT UNSIGNED NULL,
    ADD COLUMN community_publication_id BIGINT UNSIGNED NULL AFTER feedback_id,
    ADD COLUMN community_case_id BIGINT UNSIGNED NULL AFTER community_publication_id,
    ADD CONSTRAINT fk_notification_publication FOREIGN KEY (community_publication_id)
        REFERENCES community_publications (id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_notification_governance_case FOREIGN KEY (community_case_id)
        REFERENCES community_governance_cases (id) ON DELETE RESTRICT,
    ADD CONSTRAINT ck_notifications_notification_kind CHECK (
        kind IN (
            'assignment_published', 'feedback_created',
            'community_publication_changed', 'community_case_resolved'
        )
    ),
    ADD CONSTRAINT ck_notifications_notification_target CHECK (
        (kind = 'assignment_published' AND assignment_id IS NOT NULL
            AND feedback_id IS NULL AND community_publication_id IS NULL
            AND community_case_id IS NULL)
        OR (kind = 'feedback_created' AND assignment_id IS NOT NULL
            AND feedback_id IS NOT NULL AND community_publication_id IS NULL
            AND community_case_id IS NULL)
        OR (kind = 'community_publication_changed' AND assignment_id IS NULL
            AND feedback_id IS NULL AND community_publication_id IS NOT NULL
            AND community_case_id IS NULL)
        OR (kind = 'community_case_resolved' AND assignment_id IS NULL
            AND feedback_id IS NULL AND community_publication_id IS NULL
            AND community_case_id IS NOT NULL)
    );

INSERT INTO community_publications (
    project_id, owner_user_id, kind, status, revision,
    submitted_at, published_at, created_at, updated_at
)
SELECT
    projects.id,
    projects.owner_id,
    'work',
    'legacy_review_required',
    1,
    COALESCE(projects.published_at, projects.updated_at),
    COALESCE(projects.published_at, projects.updated_at),
    projects.created_at,
    projects.updated_at
FROM projects
WHERE projects.is_published = TRUE;

INSERT INTO community_publication_versions (
    publication_id, version_number, request_key, project_updated_at, kind,
    name, description, difficulty, project_status, language, framework,
    frontend, backend, `database`, repository_url, tag_names,
    attribution, source_license_statement, ai_assistance_statement,
    human_review_statement, submitted_at
)
SELECT
    publication.id,
    1,
    CONCAT('legacy-', project.id),
    project.updated_at,
    'work',
    project.name,
    project.description,
    project.difficulty,
    project.status,
    project.language,
    project.framework,
    project.frontend,
    project.backend,
    project.`database`,
    project.repository_url,
    COALESCE((
        SELECT JSON_ARRAYAGG(tag.name)
        FROM project_tags link
        JOIN tags tag ON tag.id = link.tag_id
        WHERE link.project_id = project.id
    ), JSON_ARRAY()),
    NULL,
    NULL,
    NULL,
    NULL,
    COALESCE(project.published_at, project.updated_at)
FROM community_publications publication
JOIN projects project ON project.id = publication.project_id
WHERE publication.status = 'legacy_review_required';

UPDATE community_publications
SET public_version_number = 1,
    pending_version_number = 1
WHERE status = 'legacy_review_required';

INSERT INTO community_governance_actions (
    actor_user_id, target_owner_user_id, publication_id,
    publication_version_number, comment_id, action, from_status, to_status,
    reason, target_excerpt, occurred_at
)
SELECT
    publication.owner_user_id,
    publication.owner_user_id,
    publication.id,
    1,
    NULL,
    'apply',
    'legacy_published',
    'legacy_review_required',
    'P21 迁移：历史公开内容等待人工审核',
    version.name,
    version.submitted_at
FROM community_publications publication
JOIN community_publication_versions version
    ON version.publication_id = publication.id AND version.version_number = 1
WHERE publication.status = 'legacy_review_required';
