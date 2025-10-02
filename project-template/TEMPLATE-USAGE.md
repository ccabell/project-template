# Project Template Usage Guide

## Overview

This is your **Collaborative Project Template** designed for creating new projects with GitHub integration, database connectivity, and external collaboration support while keeping your core code private.

## Key Features

✅ **Collaboration-Ready**: Complete API and infrastructure documentation for external contributors  
✅ **Database Integration**: Reference database for development + production schema documentation  
✅ **Multi-Language Support**: Node.js/Express or Python/FastAPI  
✅ **GitHub Integration**: Automated repository setup and configuration  
✅ **Security-First**: Environment-based configuration with proper secrets management  
✅ **Warp Integration**: Access to reference database through Warp environment  

## Quick Start

### Create a New Project

```powershell
# Basic Node.js project
.\scripts\create-new-project.ps1 -ProjectName "my-new-project" -ProjectPath "C:\Users\Chris\Projects" -NodeJS -InitializeGit

# Python project with GitHub repo creation
.\scripts\create-new-project.ps1 -ProjectName "api-service" -ProjectPath "C:\Users\Chris\Projects" -Python -InitializeGit -CreateGitHubRepo -GitHubUsername "your-github-username"

# Full featured project
.\scripts\create-new-project.ps1 -ProjectName "collaborative-app" -ProjectPath "C:\Users\Chris\Projects" -ProjectDescription "A collaborative application" -AuthorName "Your Name" -NodeJS -InitializeGit -CreateGitHubRepo -GitHubUsername "your-github-username"
```

### Script Parameters

| Parameter | Required | Description | Default |
|-----------|----------|-------------|---------|
| `ProjectName` | ✅ | Name of the new project | - |
| `ProjectPath` | ✅ | Directory where project will be created | - |
| `ProjectDescription` | ❌ | Project description | "A new project created from template" |
| `AuthorName` | ❌ | Author name for project files | Current Windows user |
| `GitHubUsername` | ❌ | GitHub username for repository links | "" |
| `NodeJS` | ❌ | Create Node.js/Express project | Default if neither specified |
| `Python` | ❌ | Create Python/FastAPI project | - |
| `InitializeGit` | ❌ | Initialize Git repository | - |
| `CreateGitHubRepo` | ❌ | Create GitHub repository (requires GitHub CLI) | - |

## Generated Project Structure

```
new-project/
├── src/                    # Your application code
│   ├── index.js           # Node.js entry point
│   └── main.py            # Python entry point
├── config/                 # Configuration files
│   └── database.example.json
├── docs/                   # 📚 PUBLIC documentation for collaborators
│   ├── api-documentation.md      # Complete API reference
│   ├── database-schema.md        # Production database schema
│   └── infrastructure.md         # System architecture
├── database/               # 🔒 INTERNAL database reference
│   └── schema-reference.md       # Development database access
├── scripts/                # Automation scripts
│   ├── create-new-project.ps1    # Template replication script
│   └── setup-github.ps1          # GitHub integration
├── tests/                  # Test files
├── .env.example           # Environment template
├── .gitignore             # Comprehensive gitignore
├── package.json           # Node.js dependencies (if Node.js)
├── requirements.txt       # Python dependencies (if Python)
├── project.json           # Project metadata
├── README.md              # Project overview
└── SETUP.md               # Generated setup instructions
```

## Collaboration Model

### 🤝 What External Collaborators Get Access To

- **Complete API Documentation**: Every endpoint, parameter, and response format
- **Database Schema**: Production database structure and relationships  
- **Infrastructure Overview**: System architecture and deployment information
- **Development Guidelines**: How to contribute and develop features
- **Issue Tracking**: GitHub issues and project management

### 🔒 What Remains Private

- **Core Application Code**: Your proprietary business logic
- **Production Credentials**: Database passwords, API keys, secrets
- **Deployment Scripts**: Internal deployment and infrastructure code
- **Reference Database**: Direct access to development database

### 🏗️ Database Strategy

**Development Reference Database**:
- URL: `https://pma.nextnlp.com/`
- Access: Available to Warp users only
- Purpose: Sample data and schema reference for development
- **Critical**: NOT available in production environments

**Production Database**:
- Documented schema in `/docs/database-schema.md`
- Environment-specific configuration
- Proper security and access controls
- Independent of reference database

## Setting Up Your Warp Environment

### 1. Save This Template Location

Add this to your Warp rules or bookmark:
```
Template Location: C:\Users\Chris\Projects\project-template-master
```

### 2. Create an Alias for Quick Project Creation

Add to your PowerShell profile:
```powershell
function New-CollaborativeProject {
    param($Name, $Path = "C:\Users\Chris\Projects", [switch]$Python, [switch]$NodeJS = $true)
    & "C:\Users\Chris\Projects\project-template-master\scripts\create-new-project.ps1" -ProjectName $Name -ProjectPath $Path -NodeJS:$NodeJS -Python:$Python -InitializeGit
}
```

Usage: `New-CollaborativeProject -Name "my-project"`

### 3. Reference Database Access

The template includes reference database configuration:
- Credentials managed through your Warp environment
- Documented in `database/schema-reference.md` 
- Always marked as development-only in all documentation

## Best Practices

### For Project Creation

1. **Choose Descriptive Names**: Use clear, descriptive project names
2. **Update Documentation**: Always customize the API and infrastructure docs
3. **Configure Environment**: Set up `.env` file immediately after creation
4. **Review Database Schema**: Update production schema documentation to match your needs

### For Collaboration

1. **Keep Documentation Current**: Update API docs with every change
2. **Use GitHub Issues**: Track all collaboration through GitHub issues
3. **Reference Database Warning**: Always remind collaborators that reference DB is dev-only
4. **Version API Changes**: Use semantic versioning for API updates

### For Security

1. **Never Commit Secrets**: Always use environment variables
2. **Review `.gitignore`**: Ensure all sensitive files are excluded
3. **Separate Environments**: Keep development, staging, and production separate
4. **Document Security**: Update security sections in documentation

## Customization

### Adding New Languages/Frameworks

1. Create new template files in the template directory
2. Update `create-new-project.ps1` to support the new language
3. Add appropriate dependency files (package.json, requirements.txt, etc.)
4. Update documentation templates

### Modifying Documentation Templates

Templates are located in `/docs/` and can be customized:
- `api-documentation.md`: Update API structure and endpoints
- `database-schema.md`: Modify database schema templates  
- `infrastructure.md`: Customize infrastructure information

### Environment Configuration

Update `.env.example` and `config/database.example.json` with:
- Your specific environment variables
- Database connection patterns
- Service endpoint templates

## Integration with Other Tools

### Warp Integration

The template is designed to work seamlessly with:
- Warp's database access features
- Project tracking tools
- Internal web publishing tools (as mentioned in your rules)

### GitHub Integration

Supports:
- Automated repository creation
- Issue templates
- Branch protection rules
- Collaboration workflows

### Database Tools

Works with:
- phpMyAdmin (for reference database)
- Local MySQL/MariaDB instances
- Cloud database services
- Migration tools

## Troubleshooting

### Common Issues

**Git initialization fails**:
- Check if Git is installed and in PATH
- Verify you're in the correct directory
- Ensure you have write permissions

**GitHub CLI not found**:
- Install GitHub CLI: `winget install --id GitHub.cli`
- Authenticate with `gh auth login`
- Re-run the creation script

**Template files not found**:
- Verify template directory path
- Check file permissions
- Ensure all template files are present

**Database connection issues**:
- Verify Warp environment is active
- Check network connectivity to reference database
- Review database configuration files

## Updating the Template

To update this template for new projects:

1. **Modify Template Files**: Update files in this directory
2. **Test Changes**: Create a test project to verify changes work
3. **Update Version**: Update version in `project.json`
4. **Document Changes**: Update this usage guide and README

## Support

### Internal Support
- Reference this template documentation
- Check existing projects created from this template
- Review Warp-specific features and database access

### External Collaborator Support
- Direct collaborators to documentation in `/docs/` folder
- Use GitHub issues for collaboration questions
- Maintain API documentation for integration support

---

## Quick Reference Commands

```powershell
# Create basic Node.js project
.\scripts\create-new-project.ps1 -ProjectName "project-name" -ProjectPath "C:\Users\Chris\Projects" -InitializeGit

# Create Python project with GitHub
.\scripts\create-new-project.ps1 -ProjectName "api-project" -ProjectPath "C:\Users\Chris\Projects" -Python -InitializeGit -CreateGitHubRepo -GitHubUsername "your-username"

# Full-featured collaborative project
.\scripts\create-new-project.ps1 -ProjectName "collab-app" -ProjectPath "C:\Users\Chris\Projects" -ProjectDescription "Collaborative application" -AuthorName "Your Name" -GitHubUsername "your-username" -NodeJS -InitializeGit -CreateGitHubRepo
```

Happy project creation! 🚀