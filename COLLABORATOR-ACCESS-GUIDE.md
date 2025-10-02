# B360 Collaborator Access Guide

## 🎯 Welcome to B360!

This repository contains the shared development environment for collaborative projects. You now have access to the complete project template system.

## 📍 What You Have Access To

### Project Template System
**Location**: `./project-template/`

This folder contains the complete **Collaborative Project Template System** that Chris has developed. It includes:

- ✅ **All Project Creation Scripts** - Create new projects instantly
- ✅ **Complete Documentation** - API docs, architecture guides, usage instructions
- ✅ **PowerShell Integration** - Convenient shortcuts and functions
- ✅ **Multiple Project Types** - General, A360, and production mirror projects

### Core A360 Projects
- `./web-app/` - A360 web application
- `./page-craft-bliss-forge-api/` - PageCraft API service  
- `./medplum/` - Medplum integration
- `./ios-app/` - iOS application

## 🚀 Getting Started

### 1. Access the Template System
```powershell
cd project-template
```

### 2. Read the Documentation
Start with these files in order:
1. `PROJECT-SUMMARY-EXPORT.md` - Complete system overview
2. `TEMPLATE-USAGE.md` - How to use the templates
3. `README.md` - Template system introduction

### 3. Create Your First Project
```powershell
# General collaborative project
.\scripts\create-new-project.ps1 -ProjectName "my-project" -ProjectPath "C:\path\to\projects" -NodeJS -InitializeGit

# A360 ecosystem project (if you have A360 access)
.\scripts\create-a360-project.ps1 -ProjectName "integration-service" -ProjectType "api" -Python
```

## 📋 Project Creation Options

### General Collaborative Projects
**Use Case**: Standard projects with external collaboration features
**Script**: `.\scripts\create-new-project.ps1`
**Features**: API docs, database schema, GitHub integration

### A360 Ecosystem Projects  
**Use Case**: Projects that integrate with the A360 platform
**Script**: `.\scripts\create-a360-project.ps1`
**Features**: A360-specific config and integration

### Production Mirror Base Projects
**Use Case**: Advanced projects with production repository snapshots
**Script**: `.\scripts\new-base-project.ps1`
**Features**: Safe production-like environment for collaboration

## 🔐 Access Levels

### What You Can Access
- ✅ Project template system and all scripts
- ✅ Complete documentation and guides
- ✅ Code snapshots and reference materials
- ✅ Database schema documentation
- ✅ API documentation and examples

### What Remains Protected
- 🔒 Direct production repository access (handled through snapshots)
- 🔒 Production database credentials
- 🔒 Sensitive configuration files

## 📊 Database Integration

### For Development Reference
- **Database Access**: Some projects may include reference database access
- **Important**: Reference databases are for development only
- **Production**: Always use proper production database configurations
- **Schema**: Complete database schema documentation available in project docs

## 🛠️ PowerShell Integration (Optional)

If you want to add convenient shortcuts to your PowerShell profile:

1. **Find your profile**: Run `$PROFILE` in PowerShell
2. **Edit profile**: Run `notepad $PROFILE`
3. **Add functions**: Copy content from `.\scripts\powershell-profile-addition.ps1`

After setup, you can use shortcuts like:
```powershell
ncp "project-name"        # New Collaborative Project
na360 "service-name"      # New A360 Project  
goa360                    # Go to A360 projects
```

## 🔄 Development Workflow

### Standard Workflow
1. **Create Project**: Use template scripts to create new project
2. **Set Up Environment**: Configure `.env` file with your settings
3. **Install Dependencies**: `npm install` or `pip install -r requirements.txt`
4. **Start Development**: Follow project-specific setup instructions
5. **Collaborate**: Use GitHub for version control and collaboration

### Working with Existing Projects
1. **Review Snapshots**: Study existing code in project snapshots
2. **Understand APIs**: Read API documentation thoroughly  
3. **Local Development**: Set up local database using provided schema
4. **Contribute**: Create separate repositories for your contributions

## 📚 Key Documentation Files

### In `./project-template/`:
- `PROJECT-SUMMARY-EXPORT.md` - **START HERE** - Complete system overview
- `TEMPLATE-USAGE.md` - How to use templates effectively
- `PRODUCTION-MIRROR-ARCHITECTURE.md` - Advanced architecture details
- `README.md` - Template system introduction

### In `./project-template/docs/`:
- `api-documentation.md` - API reference template
- `database-schema.md` - Database structure template  
- `infrastructure.md` - System architecture template

## 🆘 Troubleshooting

### Can't Run Scripts
**Issue**: PowerShell execution policy  
**Solution**: `Set-ExecutionPolicy RemoteSigned -CurrentUser`

### GitHub Integration Issues  
**Issue**: GitHub CLI not found  
**Solution**: `winget install --id GitHub.cli` then `gh auth login`

### Database Connection Issues
**Issue**: Can't connect to reference database  
**Solution**: Use local database setup as documented in project docs

### Template Files Not Found
**Issue**: Scripts can't find template files  
**Solution**: Ensure you're running scripts from the `project-template` directory

## 📞 Getting Help

### For Template System Issues:
1. **Check Documentation**: Read the comprehensive docs first
2. **Review Examples**: Look at example commands in `PROJECT-SUMMARY-EXPORT.md`
3. **GitHub Issues**: Create issues in the B360 repository
4. **Contact Chris**: For access or permissions issues

### For Project Development:
1. **Project Documentation**: Each generated project has its own docs
2. **API References**: Complete API documentation included
3. **Database Schema**: Schema docs available in each project

## 🎯 Next Steps

1. **Explore the Template**: Review `PROJECT-SUMMARY-EXPORT.md` for complete overview
2. **Create a Test Project**: Use the scripts to create a sample project
3. **Set Up Your Environment**: Configure PowerShell profile if desired
4. **Start Collaborating**: Begin working on projects using the template system

## 🔄 Keeping Updated

The template system is version-controlled and may receive updates. To get the latest:

1. **Pull B360 Repository**: `git pull` to get latest template updates
2. **Review Changes**: Check for updates in template documentation
3. **Update Projects**: Apply any new template features to existing projects

---

**Welcome to collaborative development with the B360 environment!** 🚀

The template system provides everything you need to create professional, well-documented projects with proper collaboration workflows. Start by reading the complete documentation, then create your first project to see the system in action.

For any questions or issues, create a GitHub issue in this repository or contact Chris directly.