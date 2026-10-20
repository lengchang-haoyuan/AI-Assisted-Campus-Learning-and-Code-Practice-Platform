-- S05: approved two analytics tables only.

CREATE TABLE analytics_batches (
	batch_id CHAR(36) NOT NULL,
	owner_user_id BIGINT UNSIGNED NOT NULL,
	period_start DATE NOT NULL,
	period_end DATE NOT NULL,
	business_timezone VARCHAR(40) NOT NULL,
	source_cutoff DATETIME(6) NOT NULL,
	schema_version VARCHAR(64) NOT NULL,
	metric_version VARCHAR(64) NOT NULL,
	rule_version VARCHAR(64) NOT NULL,
	dataset_kind VARCHAR(16) NOT NULL,
	state VARCHAR(16) NOT NULL,
	input_counts JSON NOT NULL,
	quality JSON NOT NULL,
	topic_summary JSON NOT NULL,
	artifact_ref VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
	published_at DATETIME(6),
	CONSTRAINT pk_analytics_batches PRIMARY KEY (batch_id),
	CONSTRAINT ck_analytics_batches_valid_period CHECK (period_end >= period_start),
	CONSTRAINT ck_analytics_batches_publishable_kind CHECK (dataset_kind IN ('business','controlled')),
	CONSTRAINT ck_analytics_batches_valid_state CHECK (state IN ('prepared','failed','completed')),
	CONSTRAINT uq_analytics_source_identity UNIQUE (owner_user_id, artifact_ref, metric_version, rule_version),
	CONSTRAINT fk_analytics_batches_owner_user_id_users FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX ix_analytics_owner_state_cutoff ON analytics_batches (owner_user_id, state, source_cutoff, batch_id);

CREATE TABLE analytics_daily_metrics (
	batch_id CHAR(36) NOT NULL,
	metric_date DATE NOT NULL,
	records BIGINT UNSIGNED NOT NULL,
	known_minutes BIGINT UNSIGNED NOT NULL,
	known_duration_count BIGINT UNSIGNED NOT NULL,
	missing_duration_count BIGINT UNSIGNED NOT NULL,
	known_zero_count BIGINT UNSIGNED NOT NULL,
	ordinary_count BIGINT UNSIGNED NOT NULL,
	trusted_teaching_count BIGINT UNSIGNED NOT NULL,
	unverified_claim_count BIGINT UNSIGNED NOT NULL,
	task_total BIGINT UNSIGNED NOT NULL,
	completed BIGINT UNSIGNED NOT NULL,
	cancelled BIGINT UNSIGNED NOT NULL,
	overdue_unfinished BIGINT UNSIGNED NOT NULL,
	cohort_count BIGINT UNSIGNED NOT NULL,
	revised_count BIGINT UNSIGNED NOT NULL,
	confirmed_count BIGINT UNSIGNED NOT NULL,
	CONSTRAINT pk_analytics_daily_metrics PRIMARY KEY (batch_id, metric_date),
	CONSTRAINT ck_analytics_daily_metrics_task_counts_valid CHECK (completed <= task_total AND cancelled <= task_total),
	CONSTRAINT ck_analytics_daily_metrics_record_coverage_valid CHECK (known_duration_count + missing_duration_count = records),
	CONSTRAINT ck_analytics_daily_metrics_source_counts_valid CHECK (ordinary_count + trusted_teaching_count + unverified_claim_count = records),
	CONSTRAINT fk_analytics_daily_metrics_batch_id_analytics_batches FOREIGN KEY(batch_id) REFERENCES analytics_batches (batch_id) ON DELETE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;
