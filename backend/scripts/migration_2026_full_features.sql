-- MySQL 8：补齐说明书相关表与字段。若某列已存在会报错，可跳过该行。
-- 用法：mysql -u root -p dujian_youth < scripts/migration_2026_full_features.sql

USE dujian_youth;

CREATE TABLE IF NOT EXISTS topics (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(64) NOT NULL UNIQUE,
  description VARCHAR(512) NULL,
  post_count INT NOT NULL DEFAULT 0,
  hot INT NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_checkins (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  checkin_date DATE NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_user_day (user_id, checkin_date),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 以下 ALTER 按需执行（列已存在则忽略错误）
ALTER TABLE users ADD COLUMN invite_code VARCHAR(16) NULL UNIQUE;
ALTER TABLE users ADD COLUMN referred_by_user_id BIGINT NULL;

ALTER TABLE posts ADD COLUMN topic_id BIGINT NULL;
ALTER TABLE posts ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'published';
ALTER TABLE posts ADD COLUMN risk_score FLOAT NULL;
ALTER TABLE posts ADD COLUMN moderation_labels JSON NULL;
CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_topic ON posts(topic_id);

ALTER TABLE daily_slips ADD COLUMN fun_fact TEXT NULL;
ALTER TABLE daily_slips ADD COLUMN quizzes_json JSON NULL;

ALTER TABLE chat_sessions ADD COLUMN chat_mode VARCHAR(16) NOT NULL DEFAULT 'single';
ALTER TABLE chat_sessions ADD COLUMN group_roles_json JSON NULL;

-- 每日一牍多小题：答题记录需 quiz_index（列已存在则忽略本行报错）
ALTER TABLE user_quiz_attempts ADD COLUMN quiz_index SMALLINT NOT NULL DEFAULT 0;
