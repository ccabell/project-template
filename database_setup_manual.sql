-- A360 Project Hub Database Setup
-- Run these commands in Supabase SQL editor if automatic setup fails

-- First, drop existing simplified tables if they exist
DROP TABLE IF EXISTS public.prompts CASCADE;
DROP TABLE IF EXISTS public.projects CASCADE;

-- 1. Enhanced projects table with access control
CREATE TABLE IF NOT EXISTS public.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_shared BOOLEAN DEFAULT false,
    project_type TEXT NOT NULL CHECK (project_type IN ('transcript_generator', 'prompt_tester', 'transcript_analyzer', 'general')),
    status TEXT DEFAULT 'active',
    created_by UUID REFERENCES auth.users(id),
    config JSONB DEFAULT '{}'::jsonb
);

-- 2. User profiles with roles
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id),
    email TEXT,
    full_name TEXT,
    role TEXT DEFAULT 'external' CHECK (role IN ('admin', 'internal', 'external')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Project 1: Transcript Generation Tool - Transcripts table
CREATE TABLE IF NOT EXISTS public.transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_name TEXT,
    patient_dob DATE,
    provider TEXT,
    specialty TEXT CHECK (specialty IN ('Medspa', 'Explant', 'Venous')),
    visit_type TEXT,
    is_series BOOLEAN DEFAULT false,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 4. Project 2: Prompt Testing Tool - Enhanced prompts table
CREATE TABLE IF NOT EXISTS public.prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    variables JSONB DEFAULT '[]'::jsonb,
    category TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id),
    is_template BOOLEAN DEFAULT false
);

-- 5. Project 2: Test executions
CREATE TABLE IF NOT EXISTS public.tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transcript_id UUID,
    prompt_id UUID REFERENCES public.prompts(id),
    test_name TEXT,
    variables_filled JSONB DEFAULT '{}'::jsonb,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

-- 6. Project 2: Test results
CREATE TABLE IF NOT EXISTS public.results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id UUID REFERENCES public.tests(id),
    output TEXT,
    execution_time_ms INTEGER,
    model_used TEXT,
    tokens_used INTEGER,
    cost_usd DECIMAL(10,4),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 7. Project 3: Analysis transcripts (PHI-removed real transcripts)
CREATE TABLE IF NOT EXISTS public.analysis_transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_name TEXT NOT NULL,
    content TEXT NOT NULL,
    specialty TEXT,
    date_recorded DATE,
    keywords TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    uploaded_by UUID REFERENCES auth.users(id),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 8. Project 3: Analysis results
CREATE TABLE IF NOT EXISTS public.analysis_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    transcript_ids UUID[],
    results JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id),
    export_format TEXT,
    result_count INTEGER
);

-- 9. User project access (for granular sharing)
CREATE TABLE IF NOT EXISTS public.project_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES public.projects(id),
    user_id UUID REFERENCES auth.users(id),
    access_level TEXT DEFAULT 'read' CHECK (access_level IN ('read', 'write', 'admin')),
    granted_by UUID REFERENCES auth.users(id),
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, user_id)
);

-- 10. Activity log
CREATE TABLE IF NOT EXISTS public.activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    project_id UUID REFERENCES public.projects(id),
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id UUID,
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis_transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.activity_log ENABLE ROW LEVEL SECURITY;

-- RLS Policies

-- Projects: Users can see shared projects or projects they created/have access to
CREATE POLICY IF NOT EXISTS "project_access_policy" ON public.projects 
FOR ALL USING (
    is_shared = true OR 
    created_by = auth.uid() OR 
    EXISTS (
        SELECT 1 FROM public.project_access 
        WHERE project_id = projects.id AND user_id = auth.uid()
    )
);

-- User profiles: Users can see their own profile and admins can see all
CREATE POLICY IF NOT EXISTS "user_profiles_policy" ON public.user_profiles 
FOR ALL USING (
    id = auth.uid() OR 
    EXISTS (
        SELECT 1 FROM public.user_profiles 
        WHERE id = auth.uid() AND role = 'admin'
    )
);

-- Basic policies for other tables (authenticated users)
CREATE POLICY IF NOT EXISTS "transcripts_policy" ON public.transcripts 
FOR ALL USING (auth.uid() IS NOT NULL);

CREATE POLICY IF NOT EXISTS "prompts_policy" ON public.prompts 
FOR ALL USING (auth.uid() IS NOT NULL);

CREATE POLICY IF NOT EXISTS "tests_policy" ON public.tests 
FOR ALL USING (auth.uid() IS NOT NULL);

CREATE POLICY IF NOT EXISTS "results_policy" ON public.results 
FOR ALL USING (auth.uid() IS NOT NULL);

CREATE POLICY IF NOT EXISTS "analysis_transcripts_policy" ON public.analysis_transcripts 
FOR ALL USING (auth.uid() IS NOT NULL);

CREATE POLICY IF NOT EXISTS "analysis_results_policy" ON public.analysis_results 
FOR ALL USING (auth.uid() IS NOT NULL);

CREATE POLICY IF NOT EXISTS "project_access_policy_table" ON public.project_access 
FOR ALL USING (
    user_id = auth.uid() OR 
    EXISTS (
        SELECT 1 FROM public.user_profiles 
        WHERE id = auth.uid() AND role = 'admin'
    )
);

CREATE POLICY IF NOT EXISTS "activity_log_policy" ON public.activity_log 
FOR ALL USING (
    user_id = auth.uid() OR 
    EXISTS (
        SELECT 1 FROM public.user_profiles 
        WHERE id = auth.uid() AND role = 'admin'
    )
);

-- Seed initial projects
INSERT INTO public.projects (name, description, project_type, is_shared, config) VALUES
('Synthetic Transcript Generator', 'Generate synthetic consultation transcripts for Medspa, Explant, and Venous specialties', 'transcript_generator', false, '{"specialties": ["Medspa", "Explant", "Venous"], "visit_types": ["Initial Consultation", "Follow-up", "Treatment", "Post-Treatment"]}'),
('Prompt Testing Sandbox', 'Test and compare AI prompts against stored consultation transcripts', 'prompt_tester', true, '{"supported_formats": ["txt", "docx", "pdf"], "max_file_size": 10485760}'),
('Transcript Analysis Dashboard', 'Analyze real, PHI-stripped transcripts and extract insights', 'transcript_analyzer', false, '{"export_formats": ["csv", "xlsx"], "search_fields": ["specialty", "keywords", "date_range"]}');

-- Seed initial prompts for prompt testing
INSERT INTO public.prompts (title, content, category, is_template, variables) VALUES
('Treatment Summary', 'Summarize the treatment discussed in this transcript, including the patient''s concerns and the recommended approach.', 'summary', true, '["patient_name", "treatment_focus"]'),
('Side Effects Analysis', 'Identify and list all potential side effects mentioned in this consultation transcript.', 'analysis', true, '[]'),
('Patient Concerns', 'Extract and categorize the patient''s main concerns and questions from this consultation.', 'extraction', true, '["specialty"]');

-- Create a trigger to auto-create user profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user() 
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.user_profiles (id, email, full_name, role)
  VALUES (NEW.id, NEW.email, COALESCE(NEW.raw_user_meta_data->>'full_name', ''), 'external');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();
