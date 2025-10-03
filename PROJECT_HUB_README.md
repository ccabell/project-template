# 🏢 A360 Internal Project Hub

A comprehensive project management and prompt testing system built with Streamlit and Supabase.

## 🌟 Features

### 🔐 Authentication & User Management
- Secure user registration and login via Supabase Auth
- Role-based access control (Admin, Manager, User)
- Profile management and team collaboration

### 📊 Dashboard
- Project overview with key metrics
- Recent activity tracking
- Quick access to active projects
- Weekly activity summaries

### 📁 Project Management
- Create and organize internal projects
- Project types: General, Prompt Testing, Data Analysis, Web Development, AI Research
- Priority levels and status tracking
- Project collaboration and sharing

### 🧪 Quick Prompt Testing
- Submit and test prompts against AI models
- Organize prompts by project
- View prompt history and results
- Status tracking for prompt processing

### 🗄️ Data Management
- Secure data storage with Supabase
- Row Level Security (RLS) for data protection
- Automatic backups and version control
- Export capabilities

## 🚀 Quick Start

### For Developers
1. **Clone the repository**
2. **Install dependencies**: `pip install -r requirements.txt`
3. **Set up local secrets**: Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
4. **Run locally**: `streamlit run app.py`

### For Users
1. **Access the deployed app**: `https://your-app-name.streamlit.app`
2. **Create an account** or login with existing credentials
3. **Start creating projects** and testing prompts

## 📋 System Requirements

- **Backend**: Supabase (Database + Authentication)
- **Frontend**: Streamlit Cloud
- **Version Control**: GitHub
- **Dependencies**: See `requirements.txt`

## 🛠️ Technology Stack

- **Streamlit**: Web application framework
- **Supabase**: Backend-as-a-Service (Database + Auth)
- **Python**: Core programming language
- **PostgreSQL**: Database (via Supabase)
- **GitHub**: Version control and CI/CD

## 📖 Documentation

- **Deployment Guide**: `DEPLOYMENT_GUIDE.md` - Complete setup instructions
- **Database Schema**: `database_schema.sql` - Full database structure
- **API Documentation**: Built-in Streamlit interface documentation

## 🔒 Security Features

- **Row Level Security (RLS)**: Database-level access control
- **Authentication**: Supabase Auth with email verification
- **Data Encryption**: All data encrypted in transit and at rest
- **Role-based Access**: Admin, Manager, User roles with different permissions

## 🤝 Team Collaboration

- **Multi-user Support**: Multiple team members can work simultaneously
- **Project Sharing**: Share projects with team members
- **Activity Tracking**: Monitor team activity and project progress
- **Role Management**: Assign different access levels to team members

## 📈 Monitoring & Analytics

- **User Activity**: Track login, project creation, prompt submissions
- **Project Statistics**: Monitor project progress and completion rates
- **System Health**: Built-in monitoring via Streamlit Cloud
- **Database Metrics**: Monitor via Supabase dashboard

## 🔄 Maintenance

### Regular Tasks
- **Weekly**: Review user activity and system performance
- **Monthly**: Update dependencies and review access permissions  
- **Quarterly**: Full data backup and security review

### Updates
- **Code updates**: Push to GitHub for auto-deployment
- **Database changes**: Apply via Supabase SQL Editor
- **Configuration**: Update via Streamlit Cloud settings

## 🆘 Support

### Getting Help
1. **Check the documentation** in this repository
2. **Review Streamlit Cloud logs** for app issues
3. **Check Supabase dashboard** for database issues
4. **Contact administrator**: ccabell@aesthetics360.com

### Common Issues
- **Login problems**: Check email confirmation and password
- **Project access**: Verify project permissions and collaborator status
- **Performance**: Check internet connection and clear browser cache

## 🎯 Use Cases

### Project Types Supported
- **General Projects**: Basic project management and tracking
- **Prompt Testing**: AI prompt development and testing
- **Data Analysis**: Data science and analytics projects
- **Web Development**: Website and application development
- **AI Research**: Machine learning and AI experimentation

### Typical Workflows
1. **Create Project** → Set up new internal project
2. **Add Collaborators** → Invite team members
3. **Test Prompts** → Develop and test AI prompts
4. **Track Progress** → Monitor project status and activity
5. **Export Results** → Download data and reports

## 🔮 Future Enhancements

### Planned Features
- **File Upload**: Support for document and image uploads
- **Advanced Analytics**: Detailed reporting and dashboards
- **API Integration**: Connect with external services
- **Mobile App**: Native mobile application
- **Advanced Collaboration**: Real-time editing and comments

### Customization Options
- **Branding**: Custom colors, logos, and themes
- **Project Types**: Add custom project categories
- **Workflows**: Custom approval and review processes
- **Integrations**: Connect with existing tools and services

---

## 📞 Contact & Support

**Administrator**: ccabell@aesthetics360.com
**Documentation**: See `DEPLOYMENT_GUIDE.md` for detailed setup
**Repository**: GitHub repository with full source code
**Live App**: Access via your deployed Streamlit Cloud URL

---

*Built with ❤️ for A360 internal projects*