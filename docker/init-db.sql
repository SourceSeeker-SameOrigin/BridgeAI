-- ============================================================
-- BridgeAI Database Initialization Script
-- ============================================================

-- Enable uuid-ossp for uuid generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. Tenants
-- ============================================================
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(128) NOT NULL UNIQUE,
    plan VARCHAR(64) NOT NULL DEFAULT 'free',
    config JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tenants_slug ON tenants (slug);
CREATE INDEX idx_tenants_is_active ON tenants (is_active);

-- ============================================================
-- 2. Users
-- ============================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    username VARCHAR(128) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(64) NOT NULL DEFAULT 'user',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, username),
    UNIQUE (tenant_id, email)
);

CREATE INDEX idx_users_tenant_id ON users (tenant_id);
CREATE INDEX idx_users_email ON users (email);

-- ============================================================
-- 3. API Keys
-- ============================================================
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    prefix VARCHAR(16) NOT NULL,
    scopes JSONB NOT NULL DEFAULT '[]',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_keys_tenant_id ON api_keys (tenant_id);
CREATE INDEX idx_api_keys_key_hash ON api_keys (key_hash);

-- ============================================================
-- 4. Knowledge Bases
-- ============================================================
CREATE TABLE knowledge_bases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    embedding_model VARCHAR(128) NOT NULL DEFAULT 'bge-m3',
    chunk_size INT NOT NULL DEFAULT 512,
    chunk_overlap INT NOT NULL DEFAULT 64,
    status VARCHAR(64) NOT NULL DEFAULT 'active',
    config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_knowledge_bases_tenant_id ON knowledge_bases (tenant_id);

-- ============================================================
-- 5. Knowledge Documents
-- ============================================================
CREATE TABLE knowledge_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    filename VARCHAR(512) NOT NULL,
    file_type VARCHAR(64) NOT NULL,
    file_size BIGINT NOT NULL DEFAULT 0,
    file_url TEXT,
    status VARCHAR(64) NOT NULL DEFAULT 'pending',
    chunk_count INT NOT NULL DEFAULT 0,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_knowledge_documents_kb_id ON knowledge_documents (knowledge_base_id);
CREATE INDEX idx_knowledge_documents_tenant_id ON knowledge_documents (tenant_id);
CREATE INDEX idx_knowledge_documents_status ON knowledge_documents (status);

-- ============================================================
-- 6. Knowledge Chunks
-- ============================================================
CREATE TABLE knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    chunk_index INT NOT NULL DEFAULT 0,
    token_count INT NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_knowledge_chunks_doc_id ON knowledge_chunks (document_id);
CREATE INDEX idx_knowledge_chunks_kb_id ON knowledge_chunks (knowledge_base_id);
CREATE INDEX idx_knowledge_chunks_tenant_id ON knowledge_chunks (tenant_id);

-- ============================================================
-- 7. Agents
-- ============================================================
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    parent_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    task_key VARCHAR(128),
    system_prompt TEXT,
    knowledge_base_id UUID REFERENCES knowledge_bases(id) ON DELETE SET NULL,
    model_config JSONB NOT NULL DEFAULT '{}',
    tools JSONB NOT NULL DEFAULT '[]',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agents_tenant_id ON agents (tenant_id);
CREATE INDEX idx_agents_parent_id ON agents (parent_agent_id);
CREATE INDEX idx_agents_task_key ON agents (task_key);

-- ============================================================
-- 8. Conversations
-- ============================================================
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    title VARCHAR(512),
    status VARCHAR(64) NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_tenant_id ON conversations (tenant_id);
CREATE INDEX idx_conversations_user_id ON conversations (user_id);
CREATE INDEX idx_conversations_agent_id ON conversations (agent_id);
CREATE INDEX idx_conversations_status ON conversations (status);

-- ============================================================
-- 9. Messages
-- ============================================================
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    intent VARCHAR(128),
    emotion VARCHAR(128),
    task_key VARCHAR(128),
    model_used VARCHAR(128),
    response_time_ms INT,
    first_token_ms INT,
    system_prompt_snapshot TEXT,
    token_input INT NOT NULL DEFAULT 0,
    token_output INT NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_id ON messages (conversation_id);
CREATE INDEX idx_messages_tenant_id ON messages (tenant_id);
CREATE INDEX idx_messages_role ON messages (role);
CREATE INDEX idx_messages_intent ON messages (intent);
CREATE INDEX idx_messages_created_at ON messages (created_at);

-- ============================================================
-- 10. Message Intents
-- ============================================================
CREATE TABLE message_intents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    intent VARCHAR(128) NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_message_intents_message_id ON message_intents (message_id);
CREATE INDEX idx_message_intents_intent ON message_intents (intent);

-- ============================================================
-- 11. Message Emotions
-- ============================================================
CREATE TABLE message_emotions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    emotion VARCHAR(128) NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_message_emotions_message_id ON message_emotions (message_id);
CREATE INDEX idx_message_emotions_emotion ON message_emotions (emotion);

-- ============================================================
-- 12. Message Ratings
-- ============================================================
CREATE TABLE message_ratings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    feedback TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_message_ratings_message_id ON message_ratings (message_id);

-- ============================================================
-- 13. Agent Memories
-- ============================================================
CREATE TABLE agent_memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    memory_type VARCHAR(64) NOT NULL DEFAULT 'episodic',
    importance FLOAT NOT NULL DEFAULT 0.5,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_memories_agent_id ON agent_memories (agent_id);
CREATE INDEX idx_agent_memories_tenant_id ON agent_memories (tenant_id);
CREATE INDEX idx_agent_memories_user_id ON agent_memories (user_id);
CREATE INDEX idx_agent_memories_type ON agent_memories (memory_type);

-- ============================================================
-- 14. MCP Connectors
-- ============================================================
CREATE TABLE mcp_connectors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    connector_type VARCHAR(64) NOT NULL,
    endpoint_url TEXT NOT NULL,
    auth_config JSONB NOT NULL DEFAULT '{}',
    capabilities JSONB NOT NULL DEFAULT '[]',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_mcp_connectors_tenant_id ON mcp_connectors (tenant_id);
CREATE INDEX idx_mcp_connectors_type ON mcp_connectors (connector_type);

-- ============================================================
-- 15. MCP Audit Logs
-- ============================================================
CREATE TABLE mcp_audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connector_id UUID NOT NULL REFERENCES mcp_connectors(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(128) NOT NULL,
    request_payload JSONB,
    response_payload JSONB,
    status VARCHAR(64) NOT NULL DEFAULT 'success',
    error_message TEXT,
    duration_ms INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_mcp_audit_logs_connector_id ON mcp_audit_logs (connector_id);
CREATE INDEX idx_mcp_audit_logs_tenant_id ON mcp_audit_logs (tenant_id);
CREATE INDEX idx_mcp_audit_logs_action ON mcp_audit_logs (action);
CREATE INDEX idx_mcp_audit_logs_created_at ON mcp_audit_logs (created_at);

-- ============================================================
-- 16. Installed Plugins
-- ============================================================
CREATE TABLE installed_plugins (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    plugin_name VARCHAR(255) NOT NULL,
    plugin_version VARCHAR(64) NOT NULL DEFAULT '1.0.0',
    description TEXT,
    config JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    installed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, plugin_name)
);

CREATE INDEX idx_installed_plugins_tenant_id ON installed_plugins (tenant_id);

-- ============================================================
-- 17. Usage Records
-- ============================================================
CREATE TABLE usage_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    resource_type VARCHAR(64) NOT NULL,
    quantity FLOAT NOT NULL DEFAULT 0,
    unit VARCHAR(32) NOT NULL DEFAULT 'tokens',
    model VARCHAR(128),
    metadata JSONB NOT NULL DEFAULT '{}',
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_usage_records_tenant_id ON usage_records (tenant_id);
CREATE INDEX idx_usage_records_user_id ON usage_records (user_id);
CREATE INDEX idx_usage_records_resource_type ON usage_records (resource_type);
CREATE INDEX idx_usage_records_recorded_at ON usage_records (recorded_at);

-- ============================================================
-- Seed Data
-- ============================================================

-- Default tenant
INSERT INTO tenants (id, name, slug, plan, config)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Default Tenant',
    'default',
    'free',
    '{"max_agents": 10, "max_knowledge_bases": 5}'
);

-- Admin user (password: admin123)
INSERT INTO users (id, tenant_id, username, email, password_hash, role)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    'admin',
    'admin@bridgeai.local',
    '$2b$12$gNqA2p7.MHCg2u3osOIQz.9nVZEjgbrqZ.ZYz./1JWEc8tUGgphWq',
    'admin'
);
