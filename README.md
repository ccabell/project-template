# A360 Internal Project Hub

A comprehensive project management system built according to Warp AI Build Instructions, featuring three main projects with access control, user roles, and complete database integration.

## 🚀 System Overview

This is the complete implementation of the A360 Internal Project Hub with:
- **Main Login Screen** with project menu and access control
- **User Roles**: Admin, Internal, External with proper permissions
- **Project 1**: Synthetic Transcript Generator
- **Project 2**: Prompt Testing Sandbox  
- **Project 3**: Transcript Analysis Dashboard
- **Full Database Integration**: Supabase with RLS policies

## 📁 Repository Structure

### Core Application Files
- **`main_app.py`** - Enhanced main application (RECOMMENDED)
- **`app.py`** - Original simpler application
- **`SETUP_GUIDE.md`** - Complete setup instructions

### Database Setup
- **`database_setup_manual.sql`** - Complete SQL schema for manual setup
- **`setup_complete_database.py`** - Automated database setup script
- **`create_tables.py`** - Legacy table creation

### Configuration
- **`.streamlit/secrets.toml`** - Supabase credentials
- **`.streamlit/config.toml`** - UI theme and server settings

### Legacy Files
- **`database.py`** - SQLite database functions (legacy)
- **`streamlit_app.py`** - Simple prompt tester (legacy)
- **`simple_app.py`** - Basic Streamlit interface

## ⚡ Quick Start

### 1. Database Setup (Required First)
```bash
# Go to Supabase dashboard and run the SQL commands from:
cat database_setup_manual.sql
# Copy and paste into Supabase SQL Editor
```

### 2. Install Dependencies
```bash
pip install streamlit supabase pandas python-docx PyPDF2
```

### 3. Run the Application
```bash
# Enhanced version with all features (RECOMMENDED)
streamlit run main_app.py

# Or original simpler version
streamlit run app.py
```

### 4. Access the System
1. Create account (starts as 'external' user)
2. Login and explore available projects
3. For admin access, manually update role in Supabase

## 🎯 Project Features

### Project 1: Synthetic Transcript Generator
- **Purpose**: Generate realistic consultation transcripts for training
- **Specialties**: Medspa, Explant, Venous treatments
- **Options**: Complexity levels, focus areas, series tracking
- **Integration**: Ready for Warp AI/N8N workflow integration
- **Storage**: Metadata tracking in Supabase

### Project 2: Prompt Testing Sandbox  
- **Purpose**: Test AI prompts against transcript data
- **Upload**: TXT, DOCX, PDF file support
- **Library**: Categorized prompt templates with variables
- **Testing**: Variable substitution, execution tracking
- **Analysis**: Side-by-side result comparison
- **Export**: JSON results with performance metrics

### Project 3: Transcript Analysis Dashboard
- **Purpose**: Analyze PHI-removed real transcripts
- **Database**: Upload, categorize, search transcripts
- **Queries**: Natural language analysis across multiple files
- **Results**: Snippet extraction with metadata
- **Export**: CSV, Excel, JSON formats
- **Filtering**: By specialty, date, keywords

## 👥 User Roles & Access Control

### Admin
- Full system access and user management
- Project sharing control
- All projects visible regardless of sharing status

### Internal
- Shared projects + projects they created
- Standard user capabilities
- Limited administrative functions

### External
- Only projects marked as shared
- Read and execute permissions
- No administrative access

## 🗄️ Database Schema

### Core Tables
- `projects` - Project definitions with sharing control
- `user_profiles` - User roles and permissions  
- `project_access` - Granular access control
- `activity_log` - System activity tracking

### Project-Specific Tables
- `transcripts` - Generated synthetic transcripts (Project 1)
- `prompts`, `tests`, `results` - Prompt testing system (Project 2) 
- `analysis_transcripts`, `analysis_results` - Analysis system (Project 3)

## 🔧 Configuration

### Supabase Setup
- Database URL and API key in `.streamlit/secrets.toml`
- Row Level Security (RLS) policies for access control
- Authentication handled by Supabase Auth

### Streamlit Configuration
- A360 branded theme colors
- Server settings for port and headless mode
- File upload limits and security settings

## 📋 Next Steps

1. **Database Setup**: Follow `SETUP_GUIDE.md` for complete instructions
2. **Testing**: Create test users with different roles
3. **Integration**: Connect Warp AI workflows for Project 1
4. **Customization**: Modify prompts and analysis queries
5. **Production**: Deploy with proper security configurations

## 📞 Support

For detailed setup instructions, see `SETUP_GUIDE.md`
For troubleshooting, check the database connection and RLS policies

---

✅ **Status**: Complete implementation of Warp AI Build Instructions
🎯 **Ready for**: Production deployment and integration
