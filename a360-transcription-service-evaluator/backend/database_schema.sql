-- Voice Actor Platform Database Schema
-- PostgreSQL database schema for the voice actor transcription platform

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(255) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'voice_actor')),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

-- Scripts table
CREATE TABLE IF NOT EXISTS scripts (
    script_id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    vertical VARCHAR(100),
    brands JSONB DEFAULT '[]',
    terms JSONB DEFAULT '[]',
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'draft')),
    created_by VARCHAR(255) REFERENCES users(user_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Script assignments table (many-to-many relationship)
CREATE TABLE IF NOT EXISTS script_assignments (
    assignment_id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    script_id VARCHAR(255) REFERENCES scripts(script_id) ON DELETE CASCADE,
    user_id VARCHAR(255) REFERENCES users(user_id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'assigned' CHECK (status IN ('assigned', 'in_progress', 'completed')),
    UNIQUE(script_id, user_id)
);

-- Recordings table
CREATE TABLE IF NOT EXISTS recordings (
    recording_id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(user_id) ON DELETE CASCADE,
    script_id VARCHAR(255) REFERENCES scripts(script_id) ON DELETE CASCADE,
    s3_key VARCHAR(500) NOT NULL,
    status VARCHAR(50) DEFAULT 'submitted' CHECK (status IN ('submitted', 'processing', 'completed', 'failed')),
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    file_size BIGINT,
    duration_seconds INTEGER
);

-- Brands table (for admin management)
CREATE TABLE IF NOT EXISTS brands (
    brand_id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(255) REFERENCES users(user_id),
    is_active BOOLEAN DEFAULT TRUE
);

-- Terms table (for admin management)
CREATE TABLE IF NOT EXISTS terms (
    term_id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name VARCHAR(255) UNIQUE NOT NULL,
    definition TEXT,
    category VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(255) REFERENCES users(user_id),
    is_active BOOLEAN DEFAULT TRUE
);

-- User configurations table (per-user ground truth settings)
CREATE TABLE IF NOT EXISTS user_configurations (
    config_id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id VARCHAR(255) REFERENCES users(user_id) ON DELETE CASCADE,
    config_name VARCHAR(255) NOT NULL,
    vertical VARCHAR(100),
    selected_brands JSONB DEFAULT '[]',
    selected_terms JSONB DEFAULT '[]',
    settings JSONB DEFAULT '{}',
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, config_name)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_scripts_created_by ON scripts(created_by);
CREATE INDEX IF NOT EXISTS idx_scripts_status ON scripts(status);
CREATE INDEX IF NOT EXISTS idx_script_assignments_user_id ON script_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_script_assignments_script_id ON script_assignments(script_id);
CREATE INDEX IF NOT EXISTS idx_recordings_user_id ON recordings(user_id);
CREATE INDEX IF NOT EXISTS idx_recordings_script_id ON recordings(script_id);
CREATE INDEX IF NOT EXISTS idx_recordings_status ON recordings(status);
CREATE INDEX IF NOT EXISTS idx_user_configurations_user_id ON user_configurations(user_id);

-- Add triggers to update updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scripts_updated_at BEFORE UPDATE ON scripts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_configurations_updated_at BEFORE UPDATE ON user_configurations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert some default data
INSERT INTO brands (name, description, is_active) VALUES 
    ('Botox', 'Botulinum toxin cosmetic treatment', true),
    ('Juvederm', 'Dermal filler brand', true),
    ('CoolSculpting', 'Non-invasive fat reduction', true)
ON CONFLICT (name) DO NOTHING;

INSERT INTO terms (name, definition, category, is_active) VALUES 
    ('consultation', 'Initial patient meeting and assessment', 'general', true),
    ('treatment plan', 'Customized approach for patient care', 'general', true),
    ('follow-up', 'Post-treatment patient check-in', 'general', true),
    ('aesthetic medicine', 'Medical specialty focused on cosmetic treatments', 'specialty', true),
    ('dermatology', 'Medical specialty focused on skin conditions', 'specialty', true)
ON CONFLICT (name) DO NOTHING;