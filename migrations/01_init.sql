CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    credit_balance BIGINT DEFAULT 0,
    is_admin BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    stripe_customer_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    key_prefix VARCHAR(50) NOT NULL,
    name VARCHAR(255) DEFAULT 'Default Key',
    is_active BOOLEAN DEFAULT true,
    rate_limit_rpm INT DEFAULT 60,
    rate_limit_tpm INT DEFAULT 100000,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS credit_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    amount BIGINT NOT NULL,
    balance_after BIGINT NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    description TEXT,
    reference_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS usage_logs (
    request_id VARCHAR(255) PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    api_key_id VARCHAR(255),
    model_requested VARCHAR(255),
    model_used VARCHAR(255),
    provider_type VARCHAR(100),
    input_tokens INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    credits_charged BIGINT DEFAULT 0,
    latency_ms INT DEFAULT 0,
    status VARCHAR(50) DEFAULT 'success',
    error_message TEXT,
    ip_address VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS credit_packages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    credits BIGINT NOT NULL,
    price_cents INT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    sort_order INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS model_pricing (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_pattern VARCHAR(255) NOT NULL,
    provider_type VARCHAR(100),
    input_cost_per_million BIGINT NOT NULL,
    output_cost_per_million BIGINT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    priority INT DEFAULT 0
);

-- Insert essential mock data
INSERT INTO credit_packages (name, credits, price_cents, sort_order) 
VALUES 
('Starter Pack', 1000000, 500, 1),
('Pro Pack', 5000000, 2000, 2)
ON CONFLICT DO NOTHING;

INSERT INTO model_pricing (model_pattern, provider_type, input_cost_per_million, output_cost_per_million, is_active, priority)
VALUES 
('gemini-.*', 'google', 50000, 200000, true, 10),
('claude-.*', 'anthropic', 150000, 750000, true, 10),
('gpt-.*', 'openai', 150000, 600000, true, 10)
ON CONFLICT DO NOTHING;
