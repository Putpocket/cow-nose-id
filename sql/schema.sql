-- 사용자 테이블
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    status TEXT NOT NULL DEFAULT 'active',
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    failed_attempts INT DEFAULT 0,
    locked_until TIMESTAMP,
    last_login_at TIMESTAMP,
    password_changed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 소유주 테이블
CREATE TABLE IF NOT EXISTS owners (
    owner_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    farm_name TEXT,
    address TEXT
);

-- 소 테이블
CREATE TABLE IF NOT EXISTS cows (
    cow_id SERIAL PRIMARY KEY,
    owner_id INT REFERENCES owners(owner_id),
    ear_tag TEXT UNIQUE,
    name TEXT,
    breed TEXT,
    sex TEXT,
    birth_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 소 이미지 테이블
CREATE TABLE IF NOT EXISTS cow_images (
    image_id SERIAL PRIMARY KEY,
    cow_id INT REFERENCES cows(cow_id),
    image_path TEXT NOT NULL,
    crop_box JSONB,
    embedding_version TEXT DEFAULT 'dinov2-base',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 비밀번호 이력
CREATE TABLE IF NOT EXISTS password_history (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 감사 로그
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id SERIAL PRIMARY KEY,
    user_id INT,
    username TEXT,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    ip_address TEXT,
    user_agent TEXT,
    detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);