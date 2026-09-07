-- ScholarHub P18 classrooms and teaching assignments migration.
-- Preconditions: P17 migration has completed and a verified backup exists.
-- This migration creates no members, classes, assignments, or real accounts.

SET time_zone = '+00:00';

CREATE TABLE teaching_classes (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(120) NOT NULL,
    course_title VARCHAR(120) NOT NULL,
    term_label VARCHAR(60) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    created_by_membership_id BIGINT UNSIGNED NOT NULL,
    revision INT NOT NULL DEFAULT 1,
    archived_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_teaching_classes PRIMARY KEY (id),
    CONSTRAINT fk_teaching_classes_created_by_membership_id_campus_memberships
        FOREIGN KEY (created_by_membership_id)
        REFERENCES campus_memberships (id) ON DELETE RESTRICT,
    CONSTRAINT ck_teaching_classes_teaching_class_status CHECK (
        status IN ('active', 'archived')
    ),
    INDEX ix_teaching_classes_status_id (status, id),
    INDEX ix_teaching_classes_creator_status (
        created_by_membership_id, status
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE class_memberships (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    class_id BIGINT UNSIGNED NOT NULL,
    campus_membership_id BIGINT UNSIGNED NOT NULL,
    member_role VARCHAR(16) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    joined_by_membership_id BIGINT UNSIGNED NOT NULL,
    joined_at DATETIME(6) NOT NULL,
    left_at DATETIME(6) NULL,
    revision INT NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_class_memberships PRIMARY KEY (id),
    CONSTRAINT uq_class_memberships_class_campus_membership
        UNIQUE (class_id, campus_membership_id),
    CONSTRAINT fk_class_memberships_class_id_teaching_classes
        FOREIGN KEY (class_id)
        REFERENCES teaching_classes (id) ON DELETE RESTRICT,
    CONSTRAINT fk_class_memberships_campus_membership_id_campus_memberships
        FOREIGN KEY (campus_membership_id)
        REFERENCES campus_memberships (id) ON DELETE RESTRICT,
    CONSTRAINT fk_class_memberships_joined_by_membership_id_campus_memberships
        FOREIGN KEY (joined_by_membership_id)
        REFERENCES campus_memberships (id) ON DELETE RESTRICT,
    CONSTRAINT ck_class_memberships_class_member_role CHECK (
        member_role IN ('teacher', 'student')
    ),
    CONSTRAINT ck_class_memberships_class_membership_status CHECK (
        status IN ('active', 'left', 'removed')
    ),
    INDEX ix_class_memberships_member_status_class (
        campus_membership_id, status, class_id
    ),
    INDEX ix_class_memberships_class_status_role (
        class_id, status, member_role
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE teaching_assignments (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    class_id BIGINT UNSIGNED NOT NULL,
    created_by_class_membership_id BIGINT UNSIGNED NOT NULL,
    title VARCHAR(160) NOT NULL,
    instructions TEXT NOT NULL,
    learning_objectives JSON NOT NULL,
    acceptance_criteria JSON NOT NULL,
    due_at DATETIME(6) NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'draft',
    source_project_id BIGINT UNSIGNED NULL,
    source_project_snapshot JSON NULL,
    revision INT NOT NULL DEFAULT 1,
    published_at DATETIME(6) NULL,
    closed_at DATETIME(6) NULL,
    archived_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_teaching_assignments PRIMARY KEY (id),
    CONSTRAINT fk_teaching_assignments_class_id_teaching_classes
        FOREIGN KEY (class_id)
        REFERENCES teaching_classes (id) ON DELETE RESTRICT,
    CONSTRAINT fk_teaching_assignments_creator_member
        FOREIGN KEY (created_by_class_membership_id)
        REFERENCES class_memberships (id) ON DELETE RESTRICT,
    CONSTRAINT fk_teaching_assignments_source_project_id_projects
        FOREIGN KEY (source_project_id)
        REFERENCES projects (id) ON DELETE SET NULL,
    CONSTRAINT ck_teaching_assignments_teaching_assignment_status CHECK (
        status IN ('draft', 'published', 'closed', 'archived')
    ),
    INDEX ix_teaching_assignments_class_status_due (
        class_id, status, due_at, id
    ),
    INDEX ix_teaching_assignments_class_published (
        class_id, published_at, id
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
