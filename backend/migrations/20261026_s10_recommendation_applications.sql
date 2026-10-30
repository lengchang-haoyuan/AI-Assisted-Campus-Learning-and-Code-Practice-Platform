-- S10: approved recommendation-to-task mapping only.
CREATE TABLE practice_recommendation_applications (
	id CHAR(36) NOT NULL,
	owner_user_id BIGINT UNSIGNED NOT NULL,
	batch_id CHAR(36) NOT NULL,
	candidate_key VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
	request_key VARCHAR(64) COLLATE utf8mb4_bin NOT NULL,
	request_payload JSON NOT NULL,
	task_id BIGINT UNSIGNED NOT NULL,
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
	CONSTRAINT pk_practice_recommendation_applications PRIMARY KEY (id),
	CONSTRAINT uq_practice_application_candidate UNIQUE (owner_user_id, batch_id, candidate_key),
	CONSTRAINT uq_practice_application_request UNIQUE (owner_user_id, request_key),
	CONSTRAINT fk_practice_recommendation_applications_owner_user_id_users FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE RESTRICT,
	CONSTRAINT fk_practice_recommendation_applications_batch_id_analyti_3c13 FOREIGN KEY(batch_id) REFERENCES analytics_batches (batch_id) ON DELETE RESTRICT,
	CONSTRAINT fk_practice_recommendation_applications_task_id_daily_tasks FOREIGN KEY(task_id) REFERENCES daily_tasks (id) ON DELETE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;
