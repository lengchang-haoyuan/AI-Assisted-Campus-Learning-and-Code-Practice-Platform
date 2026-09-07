-- ScholarHub P17 campus identity migration for an existing P01-P16 database.
-- Preconditions: run once after a verified backup. Existing users remain personal users.
-- No campus membership or administrator is created by this migration.

SET time_zone = '+00:00';

ALTER TABLE users
    ADD COLUMN auth_version INT NOT NULL DEFAULT 0 AFTER password_hash,
    ADD CONSTRAINT ck_users_auth_version_nonnegative CHECK (auth_version >= 0);

CREATE TABLE campus_memberships (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    `role` VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    verified_by_user_id BIGINT UNSIGNED NOT NULL,
    verified_at DATETIME(6) NOT NULL,
    revision INT NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_campus_memberships PRIMARY KEY (id),
    CONSTRAINT uq_campus_memberships_user_id UNIQUE (user_id),
    CONSTRAINT fk_campus_memberships_user_id_users FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_campus_memberships_verified_by_user_id_users FOREIGN KEY (verified_by_user_id) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_campus_memberships_campus_role CHECK (`role` IN ('student', 'teacher', 'administrator')),
    CONSTRAINT ck_campus_memberships_campus_membership_status CHECK (status IN ('active', 'suspended', 'revoked')),
    INDEX ix_campus_memberships_status_role_id (status, `role`, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE campus_invitations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    issued_by_user_id BIGINT UNSIGNED NOT NULL,
    target_user_id BIGINT UNSIGNED NULL,
    target_email VARCHAR(255) NULL,
    `role` VARCHAR(32) NOT NULL,
    token_digest BINARY(32) NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    consumed_by_user_id BIGINT UNSIGNED NULL,
    consumed_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_campus_invitations PRIMARY KEY (id),
    CONSTRAINT uq_campus_invitations_token_digest UNIQUE (token_digest),
    CONSTRAINT fk_campus_invitations_issued_by_user_id_users FOREIGN KEY (issued_by_user_id) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_campus_invitations_target_user_id_users FOREIGN KEY (target_user_id) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_campus_invitations_consumed_by_user_id_users FOREIGN KEY (consumed_by_user_id) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_campus_invitations_target_identity CHECK ((target_user_id IS NULL) <> (target_email IS NULL)),
    CONSTRAINT ck_campus_invitations_invited_role CHECK (`role` IN ('student', 'teacher')),
    CONSTRAINT ck_campus_invitations_campus_invitation_role CHECK (`role` IN ('student', 'teacher', 'administrator')),
    CONSTRAINT ck_campus_invitations_campus_invitation_status CHECK (status IN ('pending', 'consumed', 'revoked', 'expired')),
    INDEX ix_campus_invitations_status_expires (status, expires_at),
    INDEX ix_campus_invitations_issuer_created (issued_by_user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE password_resets (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    issued_by_user_id BIGINT UNSIGNED NOT NULL,
    token_digest BINARY(32) NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    consumed_at DATETIME(6) NULL,
    revoked_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_password_resets PRIMARY KEY (id),
    CONSTRAINT uq_password_resets_token_digest UNIQUE (token_digest),
    CONSTRAINT fk_password_resets_user_id_users FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_password_resets_issued_by_user_id_users FOREIGN KEY (issued_by_user_id) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_password_resets_single_terminal_state CHECK (consumed_at IS NULL OR revoked_at IS NULL),
    INDEX ix_password_resets_user_expires (user_id, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE account_audits (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    actor_user_id BIGINT UNSIGNED NOT NULL,
    target_user_id BIGINT UNSIGNED NULL,
    action VARCHAR(50) NOT NULL,
    outcome VARCHAR(16) NOT NULL,
    reason VARCHAR(500) NULL,
    occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT pk_account_audits PRIMARY KEY (id),
    CONSTRAINT fk_account_audits_actor_user_id_users FOREIGN KEY (actor_user_id) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_account_audits_target_user_id_users FOREIGN KEY (target_user_id) REFERENCES users (id) ON DELETE RESTRICT,
    INDEX ix_account_audits_actor_occurred (actor_user_id, occurred_at),
    INDEX ix_account_audits_target_occurred (target_user_id, occurred_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
