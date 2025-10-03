# 🌐 A360 Portal - Enhanced with Prompt Testing

The A360 Portal is your comprehensive internal web tool for project tracking, collaboration management, and AI agent testing. Perfect for sharing specific projects with external collaborators while maintaining security and control.

## ✨ Features

### 🔐 **Authentication & Security**
- Password-protected access via Supabase Auth
- User session management and timeouts
- Granular permission controls for external collaborators
- Audit logging of all user activities

### 📊 **Project Management Dashboard**
- Real-time project status tracking
- Integration with all B360 ecosystem projects:
  - MariaDB Sync Project
  - N8N Interface Project
  - PageCraft Bliss Forge API
  - Firecrawl Project
  - Warp Work Tracker
  - A360 Data Lake & Data Science
  - A360 Notes iOS & Transcription Service

### 🧪 **Advanced Prompt Testing Laboratory**
- **Single Prompt Testing**: Test individual prompts with detailed metrics
- **Batch Testing**: Process multiple prompts from CSV uploads
- **A/B Comparison**: Side-by-side model comparisons with voting
- **Performance Benchmarking**: Comprehensive testing across multiple scenarios
- **Real-time Results**: Live updates and progress tracking
- **Export Capabilities**: Download results as CSV for analysis

### 👥 **User Management**
- Create temporary test users for external collaborators
- Project-specific access controls
- Time-limited access with automatic expiration
- Collaboration tracking and management

### 🤖 **Agent Testing & Monitoring**
- Monitor active A360 agents in real-time
- Test agent performance and reliability
- Integration testing for API endpoints
- Automated health checks and status reporting

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Supabase account (for authentication and data persistence)

### Installation & Setup

```powershell
# 1. Navigate to the web portal directory
cd C:\Users\Chris\b360\a360-collaboration-hub\web-portal

# 2. Install dependencies
.\run.ps1 -Install

# 3. Configure environment
# Copy .env.example to .env and add your Supabase credentials
copy .env.example .env
notepad .env

# 4. Launch in development mode
.\run.ps1 -Dev
```

The portal will be available at: `http://localhost:8501`

### Configuration

Edit your `.env` file with the following key settings:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here

# Application Settings
APP_TITLE=A360 Portal
ENVIRONMENT=development

# Database Integration (Development Reference)
REF_DB_HOST=pma.nextnlp.com

# PageCraft Integration
PAGECRAFT_API_URL=http://localhost:8080/api
PAGECRAFT_ENABLED=true
```

## 🧪 Prompt Testing Capabilities

### Supported Agents & Models

**A360 Ecosystem:**
- A360 GenAI Agent
- DataSync Agent
- ContentCrawl Agent
- MariaDB Query Agent
- N8N Workflow Agent

**External APIs:**
- OpenAI GPT-4
- Claude 3.5 Sonnet
- Custom Agent Integration

### Testing Modes

1. **🎯 Single Prompt Testing**
   - Individual prompt evaluation
   - Advanced parameter controls (temperature, max tokens, top-p)
   - Real-time response metrics
   - Quality rating system

2. **📊 Batch Testing**
   - CSV upload support for multiple prompts
   - Progress tracking with real-time updates
   - Aggregate statistics and visualizations
   - Export results for further analysis

3. **⚖️ A/B Comparison**
   - Side-by-side model comparison
   - Performance metrics comparison
   - User voting system for response quality
   - Winner determination and tracking

4. **🏆 Performance Benchmarking**
   - Multi-scenario testing across multiple models
   - Configurable test parameters
   - Statistical analysis and visualizations
   - Comprehensive performance reports

### Data Storage & Analytics

With Supabase integration:
- All test results are automatically logged
- Historical performance tracking
- User activity monitoring
- Export capabilities for external analysis
- Real-time collaboration on test results

## 🔗 Integration Benefits

### For Third-Party Sharing

**Authentication & Access Control:**
- Secure login system for external collaborators
- Project-specific permissions
- Session management and timeouts
- Audit trail of all activities

**Data Persistence:**
- All prompt tests and results stored securely
- Historical comparisons and trend analysis
- Shared datasets between collaborators
- Backup and recovery capabilities

**Professional Deployment:**
- Production-ready multi-user system
- Scalable architecture for multiple concurrent users
- Real-time updates and notifications
- Professional UI/UX for client presentations

### For Internal Use

**Development & Testing:**
- Rapid prototyping of new prompts
- A/B testing of different approaches
- Performance benchmarking across models
- Integration testing with A360 ecosystem

**Collaboration:**
- Team sharing of test results
- Collective evaluation and rating
- Knowledge base of effective prompts
- Best practices documentation

## 📱 Usage Scenarios

### Client Demonstrations
- Show AI capabilities in real-time
- Compare different approaches side-by-side
- Demonstrate improvement over time
- Professional presentation interface

### Partner Collaboration
- Share specific testing scenarios
- Collaborative evaluation of results
- Joint development and testing
- Controlled access to proprietary models

### Internal Development
- Rapid iteration on prompt engineering
- Performance optimization testing
- Quality assurance and validation
- Model comparison and selection

## 🛠️ Advanced Features

### Real-time Updates
- Live test progress tracking
- Automatic result refresh
- Collaborative result viewing
- Real-time notifications

### Export & Analysis
- CSV export of all test results
- Historical trend analysis
- Performance comparison reports
- Custom analytics dashboards

### Security & Compliance
- Encrypted data storage
- Access logging and audit trails
- GDPR-compliant data handling
- Role-based access controls

## 🎯 Benefits Summary

**For External Sharing:**
✅ Professional, secure platform for client/partner collaboration
✅ Controlled access to specific projects and capabilities
✅ Historical tracking and progress demonstration
✅ No need to share internal development environments

**For Prompt Testing:**
✅ Comprehensive testing suite with multiple evaluation modes
✅ Data persistence and historical analysis
✅ Collaborative evaluation and team input
✅ Professional reporting and export capabilities

**For B360 Integration:**
✅ Seamless integration with existing project ecosystem
✅ Centralized management of all testing activities  
✅ Real-time monitoring of agent performance
✅ Single source of truth for AI capabilities

---

The A360 Portal transforms your internal development tools into a professional, shareable platform that maintains security while enabling powerful collaboration and testing capabilities. Perfect for client demonstrations, partner collaboration, and internal development workflows.