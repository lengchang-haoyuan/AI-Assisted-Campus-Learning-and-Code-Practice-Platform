-- ScholarHub P19 submissions, feedback, and in-app notifications migration.
-- Preconditions: P18 migration has completed and a verified backup exists.
-- This migration creates no accounts, classes, assignments, or submissions.

SET time_zone = '+00:00';

ALTER TABLE class_memberships
    ADD CONSTRAINT uq_class_member_class UNIQUE (id, class_id);

ALTER TABLE teaching_assignments
    ADD CONSTRAINT uq_assignment_class UNIQUE (id, class_id);

CREATE TABLE submissions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    class_id BIGINT UNSIGNED NOT NULL,
    assignment_id BIGINT UNSIGNED NOT NULL,
    student_membership_id BIGINT UNSIGNED NOT NULL,
    assignment_title VARCHAR(160) NOT NULL,
    assignment_due_at DATETIME(6) NOT NULL,
    latest_version_number INT NULL,
    revision INT NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_submissions PRIMARY KEY (id),
    CONSTRAINT uq_submission_student UNIQUE (assignment_id, student_membership_id),
    CONSTRAINT uq_submission_class UNIQUE (id, class_id),
    CONSTRAINT fk_submission_assignment
        FOREIGN KEY (assignment_id, class_id)
        REFERENCES teaching_assignments (id, class_id) ON DELETE RESTRICT,
    CONSTRAINT fk_submission_student
        FOREIGN KEY (student_membership_id, class_id)
        REFERENCES class_memberships (id, class_id) ON DELETE RESTRICT,
    INDEX ix_submission_student_updated (student_membership_id, updated_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE submission_versions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    submission_id BIGINT UNSIGNED NOT NULL,
    version_number INT NOT NULL,
    request_key VARCHAR(64) NOT NULL,
    request_payload JSON NOT NULL,
    summary TEXT NOT NULL,
    repository_url VARCHAR(1024) NULL,
    repository_ref VARCHAR(100) NULL,
    source_project_id BIGINT UNSIGNED NULL,
    source_project_title VARCHAR(120) NULL,
    status VARCHAR(16) NOT NULL,
    submitted_at DATETIME(6) NOT NULL,
    reviewed_at DATETIME(6) NULL,
    revision INT NOT NULL DEFAULT 1,
    CONSTRAINT pk_submission_versions PRIMARY KEY (id),
    CONSTRAINT uq_submission_version UNIQUE (submission_id, version_number),
    CONSTRAINT uq_submission_request UNIQUE (submission_id, request_key),
    CONSTRAINT fk_submission_versions_submission_id_submissions
        FOREIGN KEY (submission_id)
        REFERENCES submissions (id) ON DELETE RESTRICT,
    CONSTRAINT fk_submission_versions_source_project_id_projects
        FOREIGN KEY (source_project_id)
        REFERENCES projects (id) ON DELETE SET NULL,
    CONSTRAINT ck_submission_versions_positive_version CHECK (version_number >= 1),
    CONSTRAINT ck_submission_versions_submission_status CHECK (
        status IN ('submitted', 'returned', 'accepted')
    ),
    INDEX ix_submission_version_status_time (status, submitted_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE submissions
    ADD CONSTRAINT fk_submission_latest
        FOREIGN KEY (id, latest_version_number)
        REFERENCES submission_versions (submission_id, version_number)
        ON DELETE RESTRICT;

CREATE TABLE feedback (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    submission_id BIGINT UNSIGNED NOT NULL,
    version_number INT NOT NULL,
    class_id BIGINT UNSIGNED NOT NULL,
    teacher_membership_id BIGINT UNSIGNED NOT NULL,
    decision VARCHAR(16) NOT NULL,
    comment TEXT NOT NULL,
    created_at DATETIME(6) NOT NULL,
    learning_record_id BIGINT UNSIGNED NULL,
    CONSTRAINT pk_feedback PRIMARY KEY (id),
    CONSTRAINT uq_feedback_version UNIQUE (submission_id, version_number),
    CONSTRAINT uq_feedback_learning_record_id UNIQUE (learning_record_id),
    CONSTRAINT fk_feedback_version
        FOREIGN KEY (submission_id, version_number)
        REFERENCES submission_versions (submission_id, version_number)
        ON DELETE RESTRICT,
    CONSTRAINT fk_feedback_class
        FOREIGN KEY (submission_id, class_id)
        REFERENCES submissions (id, class_id) ON DELETE RESTRICT,
    CONSTRAINT fk_feedback_teacher
        FOREIGN KEY (teacher_membership_id, class_id)
        REFERENCES class_memberships (id, class_id) ON DELETE RESTRICT,
    CONSTRAINT fk_feedback_learning_record_id_learning_records
        FOREIGN KEY (learning_record_id)
        REFERENCES learning_records (id) ON DELETE SET NULL,
    CONSTRAINT ck_feedback_feedback_decision CHECK (
        decision IN ('accept', 'return')
    ),
    INDEX ix_feedback_teacher_created (teacher_membership_id, created_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE notifications (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    recipient_user_id BIGINT UNSIGNED NOT NULL,
    event_key VARCHAR(160) NOT NULL,
    kind VARCHAR(32) NOT NULL,
    assignment_id BIGINT UNSIGNED NOT NULL,
    feedback_id BIGINT UNSIGNED NULL,
    created_at DATETIME(6) NOT NULL,
    read_at DATETIME(6) NULL,
    CONSTRAINT pk_notifications PRIMARY KEY (id),
    CONSTRAINT uq_notification_event UNIQUE (recipient_user_id, event_key),
    CONSTRAINT fk_notifications_recipient_user_id_users
        FOREIGN KEY (recipient_user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_notifications_assignment_id_teaching_assignments
        FOREIGN KEY (assignment_id)
        REFERENCES teaching_assignments (id) ON DELETE RESTRICT,
    CONSTRAINT fk_notifications_feedback_id_feedback
        FOREIGN KEY (feedback_id)
        REFERENCES feedback (id) ON DELETE RESTRICT,
    CONSTRAINT ck_notifications_notification_kind CHECK (
        kind IN ('assignment_published', 'feedback_created')
    ),
    INDEX ix_notification_recipient_read_created (
        recipient_user_id, read_at, created_at, id
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
