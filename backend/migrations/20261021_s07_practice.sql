-- S07: approved fixed-template practice tables only.

CREATE TABLE practice_sessions (
	id CHAR(36) NOT NULL,
	owner_user_id BIGINT UNSIGNED NOT NULL,
	project_id BIGINT UNSIGNED NOT NULL,
	template_id VARCHAR(64) NOT NULL,
	template_version VARCHAR(32) NOT NULL,
	context_version INTEGER UNSIGNED NOT NULL,
	context_snapshot JSON NOT NULL,
	current_step_key VARCHAR(32) NOT NULL DEFAULT 'understand',
	status VARCHAR(32) NOT NULL DEFAULT 'ready',
	revision INTEGER UNSIGNED NOT NULL DEFAULT 1,
	active_operation_id CHAR(36),
	active_action VARCHAR(32),
	active_ai_request_id BIGINT UNSIGNED,
	step_outputs JSON NOT NULL,
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
	CONSTRAINT pk_practice_sessions PRIMARY KEY (id),
	CONSTRAINT ck_practice_sessions_context_version_positive CHECK (context_version >= 1),
	CONSTRAINT ck_practice_sessions_revision_positive CHECK (revision >= 1),
	CONSTRAINT ck_practice_sessions_valid_step CHECK (current_step_key IN ('understand','implement')),
	CONSTRAINT fk_practice_sessions_owner_user_id_users FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE RESTRICT,
	CONSTRAINT fk_practice_sessions_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
	CONSTRAINT ck_practice_sessions_practice_session_status CHECK (status IN ('ready', 'running', 'waiting_submission', 'waiting_revision', 'waiting_confirmation', 'failed', 'cancelled', 'completed')),
	CONSTRAINT fk_practice_sessions_active_ai_request_id_ai_requests FOREIGN KEY(active_ai_request_id) REFERENCES ai_requests (id) ON DELETE SET NULL
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX ix_practice_sessions_owner_created ON practice_sessions (owner_user_id, created_at, id);

CREATE INDEX ix_practice_sessions_project_status ON practice_sessions (project_id, status);

CREATE TABLE practice_attempts (
	id CHAR(36) NOT NULL,
	session_id CHAR(36) NOT NULL,
	step_key VARCHAR(32) NOT NULL,
	attempt_no INTEGER UNSIGNED NOT NULL,
	request_key VARCHAR(64) COLLATE utf8mb4_bin NOT NULL,
	code_text TEXT NOT NULL,
	declared_output JSON NOT NULL,
	self_statement BOOLEAN,
	status VARCHAR(32) NOT NULL DEFAULT 'submitted',
	operation_id CHAR(36),
	ai_request_id BIGINT UNSIGNED,
	review_schema_version VARCHAR(64),
	feedback JSON,
	reviewed_at DATETIME(6),
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
	CONSTRAINT pk_practice_attempts PRIMARY KEY (id),
	CONSTRAINT uq_practice_attempt_step_no UNIQUE (session_id, step_key, attempt_no),
	CONSTRAINT uq_practice_attempt_request UNIQUE (session_id, request_key),
	CONSTRAINT uq_practice_attempt_session_id UNIQUE (session_id, id),
	CONSTRAINT ck_practice_attempts_attempt_no_positive CHECK (attempt_no >= 1),
	CONSTRAINT ck_practice_attempts_submission_step CHECK (step_key = 'implement'),
	CONSTRAINT ck_practice_attempts_code_length CHECK (CHAR_LENGTH(code_text) <= 12000),
	CONSTRAINT fk_practice_attempts_session_id_practice_sessions FOREIGN KEY(session_id) REFERENCES practice_sessions (id) ON DELETE CASCADE,
	CONSTRAINT fk_practice_attempts_ai_request_id_ai_requests FOREIGN KEY(ai_request_id) REFERENCES ai_requests (id) ON DELETE SET NULL
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE practice_events (
	id CHAR(36) NOT NULL,
	session_id CHAR(36) NOT NULL,
	attempt_id CHAR(36),
	event_key VARCHAR(160) COLLATE utf8mb4_bin NOT NULL,
	event_type VARCHAR(48) NOT NULL,
	criterion_id VARCHAR(8),
	issue_type VARCHAR(64),
	confirmation_kind VARCHAR(32),
	occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
	action_payload JSON NOT NULL,
	CONSTRAINT pk_practice_events PRIMARY KEY (id),
	CONSTRAINT fk_practice_events_attempt_session FOREIGN KEY(session_id, attempt_id) REFERENCES practice_attempts (session_id, id) ON DELETE CASCADE,
	CONSTRAINT uq_practice_event_key UNIQUE (session_id, event_key),
	CONSTRAINT ck_practice_events_valid_criterion CHECK (criterion_id IS NULL OR criterion_id IN ('C01','C02','C03','C04','C05','C06')),
	CONSTRAINT fk_practice_events_session_id_practice_sessions FOREIGN KEY(session_id) REFERENCES practice_sessions (id) ON DELETE CASCADE
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX ix_practice_events_session_time ON practice_events (session_id, occurred_at, id);
