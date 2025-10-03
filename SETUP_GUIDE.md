# A360 Project Hub - Complete Setup Guide

## 🚀 Overview

This is a comprehensive project management system built according to the Warp AI Build Instructions, featuring:

- **Main Login Screen** with project menu and access control
- **Project 1**: Synthetic Transcript Generator
- **Project 2**: Prompt Testing Tool  
- **Project 3**: Transcript Analysis Interface
- **User Roles**: Admin, Internal, External with proper access control
- **Database**: Supabase with RLS policies

## 📋 Prerequisites

1. **Supabase Account** - Database and authentication
2. **Python 3.8+** with pip
3. **Streamlit** - Web interface framework
4. **Internet connection** - For Supabase connectivity

## 🛠️ Step-by-Step Setup

### 1. Database Setup

#### Option A: Automatic Setup (if supported)
```bash
python setup_complete_database.py
```

#### Option B: Manual Setup (Recommended)
1. Go to your Supabase dashboard: https://app.supabase.com
2. Navigate to the SQL Editor
3. Copy and paste the entire contents of `database_setup_manual.sql`
4. Execute the SQL commands
5. Verify all tables were created in the Table Editor

### 2. Install Dependencies

```bash
pip install streamlit supabase pandas python-docx PyPDF2
```

### 3. Configure Application

The application is pre-configured with the Supabase credentials from your `.streamlit/secrets.toml` file.

### 4. Run the Application

#### Option A: Use the enhanced main application
```bash
streamlit run main_app.py
```

#### Option B: Use the original application (simpler version)
```bash
streamlit run app.py
```

## 🏗️ System Architecture

### Database Schema

#### Core Tables
- **projects** - Main project definitions with sharing control
- **user_profiles** - User roles and permissions
- **project_access** - Granular project access control
- **activity_log** - System activity tracking

#### Project 1: Transcript Generator
- **transcripts** - Generated synthetic transcripts
- Metadata: patient info, specialty, visit type, generation params

#### Project 2: Prompt Tester
- **prompts** - Prompt library with variables
- **tests** - Test executions
- **results** - Test outputs with performance metrics

#### Project 3: Transcript Analyzer
- **analysis_transcripts** - PHI-removed real transcripts
- **analysis_results** - Analysis outputs with export capability

### User Roles & Access Control

#### Admin
- Full system access
- User management
- Project sharing control
- All projects visible

#### Internal
- Shared projects + own projects
- Standard user capabilities
- Limited administrative functions

#### External  
- Only shared projects
- Read/execute permissions
- No administrative access

## 🎯 Project Features

### Project 1: Synthetic Transcript Generator
- **Form Interface**: Specialty (Medspa/Explant/Venous), visit type, patient details
- **Generation Options**: Complexity, length, focus areas
- **Integration Ready**: Warp AI/N8N workflow hooks
- **Storage**: Supabase with metadata
- **Export**: Text file download

### Project 2: Prompt Testing Tool
- **Upload System**: TXT, DOCX, PDF transcript support
- **Prompt Library**: Categorized templates with variables
- **Test Runner**: Variable substitution, execution tracking
- **Results Dashboard**: Side-by-side comparison, export options
- **Performance Tracking**: Execution time, tokens, costs

### Project 3: Transcript Analysis Interface
- **Database Management**: Upload, categorize, search transcripts
- **Query System**: Natural language analysis queries
- **Bulk Analysis**: Run queries across multiple transcripts
- **Export System**: JSON, CSV, Excel formats
- **Search & Filter**: By specialty, date, keywords

## 🔧 Configuration Options

### Environment Variables (Optional)
```bash
export SUPABASE_URL="your_supabase_url"
export SUPABASE_KEY="your_supabase_key"
```

### Streamlit Configuration
Located in `.streamlit/config.toml`:
- Theme colors (A360 branding)
- Server settings
- Browser preferences

## 🚦 Testing the System

### 1. User Registration & Login
1. Run the application
2. Create a new account (starts as 'external' role)
3. Login and verify project access

### 2. Admin Setup
1. Manually update user role in Supabase:
   ```sql
   UPDATE user_profiles SET role = 'admin' WHERE email = 'your-email@domain.com';
   ```
2. Login as admin
3. Test project creation and user management

### 3. Project Testing
1. **Test Project 1**: Generate sample transcripts
2. **Test Project 2**: Upload transcripts, create prompts, run tests
3. **Test Project 3**: Upload analysis transcripts, run queries

### 4. Access Control Testing
1. Create users with different roles
2. Test project visibility based on sharing settings
3. Verify admin can manage all users/projects

## 🔍 Troubleshooting

### Database Connection Issues
- Verify Supabase credentials in `secrets.toml`
- Check RLS policies are properly configured
- Ensure user has proper database permissions

### Missing Tables
- Run the complete SQL script from `database_setup_manual.sql`
- Check Supabase logs for error messages
- Verify all foreign key relationships

### Authentication Issues
- Check Supabase Auth settings
- Verify email confirmation if enabled
- Test with different browsers/incognito mode

### Project Access Issues
- Verify user role assignment
- Check project `is_shared` status
- Review RLS policies in database

## 🚀 Production Deployment

### Environment Setup
1. Use environment variables for secrets
2. Enable HTTPS for Streamlit
3. Configure proper CORS policies
4. Set up monitoring and logging

### Security Considerations
- Enable Supabase RLS policies
- Use secure Supabase keys (not anon key in production)
- Implement proper session management
- Regular security audits

### Performance Optimization
- Enable Streamlit caching
- Optimize database queries
- Implement connection pooling
- Monitor resource usage

## 📊 Usage Analytics

The system tracks:
- User activity in `activity_log` table
- Project usage patterns
- Test execution metrics
- Analysis query performance

## 🔗 Integration Points

### Warp AI/N8N Integration
- Project 1: Transcript generation workflow hooks
- Project 2: AI model execution endpoints
- Project 3: Batch analysis processing

### Future Extensions
- API endpoints for external tools
- Webhook integrations
- Advanced analytics dashboard
- Real-time collaboration features

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Supabase dashboard logs
3. Test with simplified database queries
4. Contact system administrator

## 🎉 Success Criteria

✅ **Complete Implementation**
- All three projects fully functional
- User roles and access control working
- Database schema properly implemented
- Authentication system operational

✅ **User Workflows**
- Registration and login flow
- Project navigation and access
- Data entry and processing
- Results viewing and export

✅ **System Integration**
- Supabase connectivity
- File upload/processing
- Real-time updates
- Proper error handling

---

**Note**: This system implements the complete Warp AI Build Instructions specification with all required features for the A360 Internal Project Hub.