CREATE TABLE IF NOT EXISTS users (id uuid PRIMARY KEY, email text NOT NULL UNIQUE, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS sessions (token_hash text PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires_at timestamptz NOT NULL);
CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions(user_id);
CREATE TABLE IF NOT EXISTS email_tokens (token_hash text PRIMARY KEY, email text NOT NULL, browser_hash text NOT NULL, expires_at timestamptz NOT NULL, return_path text NOT NULL);
CREATE TABLE IF NOT EXISTS workspaces (user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, revision bigint NOT NULL DEFAULT 0, data jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS model_profiles (user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, id text NOT NULL, name text NOT NULL, provider text NOT NULL, protocol text NOT NULL, base_url text NOT NULL, model text NOT NULL, encrypted_key bytea NOT NULL, key_last4 text NOT NULL, PRIMARY KEY(user_id,id));
