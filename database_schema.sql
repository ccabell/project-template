-- A360 Internal Project Hub Database Schema
-- Run this SQL in your Supabase SQL Editor

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (extends Supabase auth.users)
CREATE TABLE public.profiles (
    id UUID REFERENCES auth.users(id) PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    role TEXT DEFAULT 'user' CHECK (role IN ('admin', 'manager', 'user')),
    department TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Projects table
CREATE TABLE public.projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed', 'archived')),
    priority TEXT DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    owner_id UUID REFERENCES public.profiles(id),
    created_by UUID REFERENCES public.profiles(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    due_date TIMESTAMPTZ,
    tags TEXT[],
    project_type TEXT DEFAULT 'general' CHECK (project_type IN ('general', 'prompt_testing', 'data_analysis', 'web_development', 'ai_research'))
);

-- Prompts table (enhanced from original)
CREATE TABLE public.prompts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES public.projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES public.profiles(id),
    prompt TEXT NOT NULL,
    response TEXT,
    model_used TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    execution_time_ms INTEGER,
    tags TEXT[]
);

-- Activity log table
CREATE TABLE public.activity_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.profiles(id),
    project_id UUID REFERENCES public.projects(id),
    activity_type TEXT NOT NULL CHECK (activity_type IN ('project_created', 'project_updated', 'prompt_submitted', 'prompt_completed', 'user_login', 'user_logout')),
    description TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Project collaborators table
CREATE TABLE public.project_collaborators (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES public.projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'collaborator' CHECK (role IN ('owner', 'manager', 'collaborator', 'viewer')),
    added_by UUID REFERENCES public.profiles(id),
    added_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, user_id)
);

-- Settings table for application configuration
CREATE TABLE public.app_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key TEXT UNIQUE NOT NULL,
    value JSONB NOT NULL,
    description TEXT,
    updated_by UUID REFERENCES public.profiles(id),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security on all tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.activity_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_collaborators ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.app_settings ENABLE ROW LEVEL SECURITY;

-- RLS Policies

-- Profiles: Users can read all profiles but only update their own
CREATE POLICY "Public profiles are viewable by everyone" ON public.profiles
    FOR SELECT USING (true);

CREATE POLICY "Users can insert their own profile" ON public.profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can update their own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

-- Projects: Users can see projects they own or collaborate on
CREATE POLICY "Users can view their projects" ON public.projects
    FOR SELECT USING (
        auth.uid() = owner_id OR 
        auth.uid() = created_by OR
        EXISTS (
            SELECT 1 FROM public.project_collaborators 
            WHERE project_id = projects.id AND user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert projects" ON public.projects
    FOR INSERT WITH CHECK (auth.uid() = created_by);

CREATE POLICY "Project owners can update projects" ON public.projects
    FOR UPDATE USING (auth.uid() = owner_id OR auth.uid() = created_by);

CREATE POLICY "Project owners can delete projects" ON public.projects
    FOR DELETE USING (auth.uid() = owner_id OR auth.uid() = created_by);

-- Prompts: Users can see prompts for projects they have access to
CREATE POLICY "Users can view prompts for accessible projects" ON public.prompts
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.projects 
            WHERE id = prompts.project_id AND (
                owner_id = auth.uid() OR 
                created_by = auth.uid() OR
                EXISTS (
                    SELECT 1 FROM public.project_collaborators 
                    WHERE project_id = projects.id AND user_id = auth.uid()
                )
            )
        )
    );

CREATE POLICY "Users can insert prompts" ON public.prompts
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own prompts" ON public.prompts
    FOR UPDATE USING (auth.uid() = user_id);

-- Activity log: Users can view their own activities and project activities
CREATE POLICY "Users can view relevant activities" ON public.activity_log
    FOR SELECT USING (
        auth.uid() = user_id OR
        EXISTS (
            SELECT 1 FROM public.projects 
            WHERE id = activity_log.project_id AND (
                owner_id = auth.uid() OR 
                created_by = auth.uid() OR
                EXISTS (
                    SELECT 1 FROM public.project_collaborators 
                    WHERE project_id = projects.id AND user_id = auth.uid()
                )
            )
        )
    );

CREATE POLICY "Users can insert activities" ON public.activity_log
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Project collaborators: Manage collaboration access
CREATE POLICY "Users can view project collaborators" ON public.project_collaborators
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.projects 
            WHERE id = project_collaborators.project_id AND (
                owner_id = auth.uid() OR 
                created_by = auth.uid() OR
                EXISTS (
                    SELECT 1 FROM public.project_collaborators pc
                    WHERE pc.project_id = projects.id AND pc.user_id = auth.uid()
                )
            )
        )
    );

CREATE POLICY "Project owners can manage collaborators" ON public.project_collaborators
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.projects 
            WHERE id = project_collaborators.project_id AND (
                owner_id = auth.uid() OR created_by = auth.uid()
            )
        )
    );

-- App settings: Only admins can manage
CREATE POLICY "Everyone can view app settings" ON public.app_settings
    FOR SELECT USING (true);

CREATE POLICY "Admins can manage app settings" ON public.app_settings
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.profiles 
            WHERE id = auth.uid() AND role = 'admin'
        )
    );

-- Functions for updating timestamps
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updating timestamps
CREATE TRIGGER on_profiles_updated
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER on_projects_updated
    BEFORE UPDATE ON public.projects
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER on_prompts_updated
    BEFORE UPDATE ON public.prompts
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- Function to create profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (NEW.id, NEW.email, NEW.raw_user_meta_data->>'full_name');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger for new user signup
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Insert default app settings
INSERT INTO public.app_settings (key, value, description) VALUES
('app_name', '"A360 Internal Project Hub"', 'Application name'),
('max_projects_per_user', '50', 'Maximum projects per user'),
('default_project_type', '"general"', 'Default project type for new projects'),
('maintenance_mode', 'false', 'Enable/disable maintenance mode'),
('allowed_file_types', '["txt", "pdf", "docx", "csv"]', 'Allowed file upload types');

-- Create indexes for better performance
CREATE INDEX idx_projects_owner ON public.projects(owner_id);
CREATE INDEX idx_projects_created_by ON public.projects(created_by);
CREATE INDEX idx_projects_status ON public.projects(status);
CREATE INDEX idx_prompts_project ON public.prompts(project_id);
CREATE INDEX idx_prompts_user ON public.prompts(user_id);
CREATE INDEX idx_activity_user ON public.activity_log(user_id);
CREATE INDEX idx_activity_project ON public.activity_log(project_id);
CREATE INDEX idx_collaborators_project ON public.project_collaborators(project_id);
CREATE INDEX idx_collaborators_user ON public.project_collaborators(user_id);

-- Create view for project statistics
CREATE VIEW public.project_stats AS
SELECT 
    p.id,
    p.name,
    p.status,
    COUNT(DISTINCT pr.id) as prompt_count,
    COUNT(DISTINCT pc.user_id) as collaborator_count,
    MAX(pr.created_at) as last_prompt_date,
    p.created_at,
    p.updated_at
FROM public.projects p
LEFT JOIN public.prompts pr ON p.id = pr.project_id
LEFT JOIN public.project_collaborators pc ON p.id = pc.project_id
GROUP BY p.id, p.name, p.status, p.created_at, p.updated_at;