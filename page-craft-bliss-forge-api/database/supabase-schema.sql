-- A360 Scraping Management Database Schema for Supabase
-- Run this in your Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Brands table (Allergan, Galderma, etc.)
CREATE TABLE brands (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  name VARCHAR(255) NOT NULL UNIQUE,
  description TEXT,
  website_url VARCHAR(500),
  logo_url VARCHAR(500),
  color_hex VARCHAR(7) DEFAULT '#3B82F6',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Product categories
CREATE TABLE product_categories (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- US Products master list
CREATE TABLE us_products (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  brand_id UUID REFERENCES brands(id) ON DELETE CASCADE,
  category_id UUID REFERENCES product_categories(id),
  name VARCHAR(255) NOT NULL,
  generic_name VARCHAR(255),
  product_code VARCHAR(100),
  fda_approval_date DATE,
  indication TEXT,
  description TEXT,
  priority_level INTEGER DEFAULT 3, -- 1=High, 2=Medium, 3=Low
  status VARCHAR(50) DEFAULT 'pending', -- pending, in_progress, scraped, failed, skipped
  official_website VARCHAR(500),
  prescribing_info_url VARCHAR(500),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Scraping projects/jobs
CREATE TABLE scraping_projects (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  brand_id UUID REFERENCES brands(id),
  product_id UUID REFERENCES us_products(id),
  base_url VARCHAR(500) NOT NULL,
  project_type VARCHAR(100) DEFAULT 'product_site', -- product_site, competitor_analysis, market_research
  status VARCHAR(50) DEFAULT 'planned', -- planned, in_progress, completed, failed, cancelled
  priority INTEGER DEFAULT 3, -- 1=High, 2=Medium, 3=Low
  
  -- Scraping configuration
  scraping_method VARCHAR(100) DEFAULT 'firecrawl', -- firecrawl, puppeteer, selenium
  max_pages INTEGER DEFAULT 100,
  max_depth INTEGER DEFAULT 3,
  include_pdfs BOOLEAN DEFAULT true,
  custom_config JSONB,
  
  -- Results tracking
  total_pages_scraped INTEGER DEFAULT 0,
  total_words_scraped INTEGER DEFAULT 0,
  total_pdfs_found INTEGER DEFAULT 0,
  total_pdfs_downloaded INTEGER DEFAULT 0,
  
  -- Timing
  started_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE,
  last_run_at TIMESTAMP WITH TIME ZONE,
  next_scheduled_run TIMESTAMP WITH TIME ZONE,
  
  -- Error tracking
  error_message TEXT,
  error_details JSONB,
  
  -- Metadata
  assigned_to VARCHAR(255), -- Who is responsible
  notes TEXT,
  tags TEXT[], -- Array of tags
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Scraped pages (summary data)
CREATE TABLE scraped_pages (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  project_id UUID REFERENCES scraping_projects(id) ON DELETE CASCADE,
  url VARCHAR(1000) NOT NULL,
  title VARCHAR(500),
  word_count INTEGER DEFAULT 0,
  content_hash VARCHAR(64),
  status VARCHAR(50) DEFAULT 'processed', -- processed, failed, skipped
  scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- PDF files tracking
CREATE TABLE scraped_pdfs (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  project_id UUID REFERENCES scraping_projects(id) ON DELETE CASCADE,
  page_id UUID REFERENCES scraped_pages(id),
  filename VARCHAR(500) NOT NULL,
  pdf_url VARCHAR(1000) NOT NULL,
  file_size_bytes BIGINT DEFAULT 0,
  file_hash VARCHAR(64),
  download_status VARCHAR(50) DEFAULT 'pending', -- pending, downloaded, failed
  storage_path VARCHAR(1000), -- Path in file storage
  extracted_text_length INTEGER DEFAULT 0,
  downloaded_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Content chunks for RAG
CREATE TABLE content_chunks (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  project_id UUID REFERENCES scraping_projects(id) ON DELETE CASCADE,
  page_id UUID REFERENCES scraped_pages(id),
  pdf_id UUID REFERENCES scraped_pdfs(id),
  chunk_text TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  chunk_size INTEGER NOT NULL,
  chunk_type VARCHAR(100) DEFAULT 'paragraph',
  embedding_status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
  embedding_model VARCHAR(100),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Project activity log
CREATE TABLE project_activities (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  project_id UUID REFERENCES scraping_projects(id) ON DELETE CASCADE,
  activity_type VARCHAR(100) NOT NULL, -- started, completed, failed, updated, note_added
  message TEXT NOT NULL,
  details JSONB,
  user_name VARCHAR(255),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_us_products_brand ON us_products(brand_id);
CREATE INDEX idx_us_products_status ON us_products(status);
CREATE INDEX idx_us_products_priority ON us_products(priority_level);

CREATE INDEX idx_scraping_projects_brand ON scraping_projects(brand_id);
CREATE INDEX idx_scraping_projects_product ON scraping_projects(product_id);
CREATE INDEX idx_scraping_projects_status ON scraping_projects(status);
CREATE INDEX idx_scraping_projects_priority ON scraping_projects(priority);

CREATE INDEX idx_scraped_pages_project ON scraped_pages(project_id);
CREATE INDEX idx_scraped_pages_url ON scraped_pages(url);

CREATE INDEX idx_scraped_pdfs_project ON scraped_pdfs(project_id);
CREATE INDEX idx_scraped_pdfs_status ON scraped_pdfs(download_status);

CREATE INDEX idx_content_chunks_project ON content_chunks(project_id);
CREATE INDEX idx_content_chunks_embedding ON content_chunks(embedding_status);

CREATE INDEX idx_project_activities_project ON project_activities(project_id);
CREATE INDEX idx_project_activities_type ON project_activities(activity_type);

-- Insert initial brands
INSERT INTO brands (name, description, website_url, color_hex) VALUES 
('Allergan', 'Leading aesthetics and medical company', 'https://www.allergan.com', '#0066CC'),
('Galderma', 'Dermatology focused pharmaceutical company', 'https://www.galderma.com', '#E31E24'),
('Revance', 'Biotechnology company focused on neuromodulators', 'https://www.revance.com', '#00A651'),
('Merz', 'Aesthetics and neurotoxin treatments', 'https://www.merz.com', '#8B1538'),
('Prollenium', 'Medical device and aesthetics company', 'https://prollenium.com', '#FF6B35');

-- Insert product categories
INSERT INTO product_categories (name, description) VALUES 
('Neuromodulators', 'Botulinum toxin products (Botox, Dysport, etc.)'),
('Dermal Fillers', 'Injectable fillers for facial enhancement'),
('Skin Care', 'Topical treatments and skin care products'),
('Body Contouring', 'Non-surgical body sculpting treatments'),
('Hair Restoration', 'Hair loss and restoration treatments'),
('Energy Devices', 'Laser and energy-based treatment devices'),
('Injectables', 'Other injectable treatments and medications');

-- Insert some initial US products for demonstration
INSERT INTO us_products (brand_id, category_id, name, generic_name, indication, priority_level, official_website) 
SELECT 
  b.id,
  pc.id,
  product_data.name,
  product_data.generic_name,
  product_data.indication,
  product_data.priority_level,
  product_data.official_website
FROM brands b
CROSS JOIN product_categories pc
CROSS JOIN (VALUES
  -- Allergan products
  ('Allergan', 'Neuromodulators', 'Botox Cosmetic', 'onabotulinumtoxinA', 'Temporary improvement in appearance of moderate to severe frown lines', 1, 'https://www.botoxcosmetic.com'),
  ('Allergan', 'Dermal Fillers', 'Juvederm', 'Hyaluronic Acid Filler', 'Add volume and smooth wrinkles and folds', 1, 'https://www.juvederm.com'),
  ('Allergan', 'Body Contouring', 'CoolSculpting', 'Cryolipolysis', 'Non-invasive fat reduction', 1, 'https://www.coolsculpting.com'),
  ('Allergan', 'Dermal Fillers', 'Voluma', 'Hyaluronic Acid Filler', 'Add volume to cheek area', 2, 'https://www.voluma.com'),
  
  -- Galderma products  
  ('Galderma', 'Neuromodulators', 'Dysport', 'abobotulinumtoxinA', 'Treatment of cervical dystonia and glabellar lines', 1, 'https://www.dysport.com'),
  ('Galderma', 'Dermal Fillers', 'Restylane', 'Hyaluronic Acid Filler', 'Add volume and fullness to skin', 1, 'https://www.restylane.com'),
  ('Galderma', 'Skin Care', 'Cetaphil', 'Gentle cleanser and moisturizer', 'Daily skin care for sensitive skin', 3, 'https://www.cetaphil.com'),
  
  -- Revance products
  ('Revance', 'Neuromodulators', 'Daxxify', 'daxibotulinumtoxinA', 'Treatment of glabellar lines', 1, 'https://www.daxxify.com')
) AS product_data(brand_name, category_name, name, generic_name, indication, priority_level, official_website)
WHERE b.name = product_data.brand_name AND pc.name = product_data.category_name;

-- Create updated_at triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_brands_updated_at BEFORE UPDATE ON brands 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_us_products_updated_at BEFORE UPDATE ON us_products 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scraping_projects_updated_at BEFORE UPDATE ON scraping_projects 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security (RLS)
ALTER TABLE brands ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE us_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraping_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraped_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraped_pdfs ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_activities ENABLE ROW LEVEL SECURITY;

-- Create policies (allowing all operations for authenticated users for now)
CREATE POLICY "Allow all operations for authenticated users" ON brands FOR ALL TO authenticated USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON product_categories FOR ALL TO authenticated USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON us_products FOR ALL TO authenticated USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON scraping_projects FOR ALL TO authenticated USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON scraped_pages FOR ALL TO authenticated USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON scraped_pdfs FOR ALL TO authenticated USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON content_chunks FOR ALL TO authenticated USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON project_activities FOR ALL TO authenticated USING (true);

-- Allow read access for anonymous users (for public dashboard if needed)
CREATE POLICY "Allow read access for anonymous users" ON brands FOR SELECT TO anon USING (true);
CREATE POLICY "Allow read access for anonymous users" ON product_categories FOR SELECT TO anon USING (true);
CREATE POLICY "Allow read access for anonymous users" ON us_products FOR SELECT TO anon USING (true);
CREATE POLICY "Allow read access for anonymous users" ON scraping_projects FOR SELECT TO anon USING (true);