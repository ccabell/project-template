# Production Mirror Architecture

## Overview

This document describes the production-mirrored base project architecture designed for collaborative development while maintaining direct access to production repositories.

## 🏗️ Architecture Goals

1. **Direct Production Development**: Work directly against production repositories in real-time
2. **Safe Collaboration**: Provide realistic environment for external developers without production access
3. **B360 Shared Environment**: All projects live in B360 for easy sharing and management
4. **Database Integration**: Reference database for development, snapshots for collaborators

## 📊 Project Structure

```
B360/
├── web-app/                           # Production: a360-web-app-develop
├── page-craft-bliss-forge-api/       # Production: optional integration
├── [your-base-project]/              # Your new base project
│   ├── production-repos/             # Symbolic links to production repos
│   │   ├── a360-genai-platform-develop/  -> ../../mariadb-sync-project/a360-genai-platform-develop
│   │   ├── a360-web-app-develop/         -> ../web-app
│   │   └── page-craft-bliss-forge-api/   -> ../page-craft-bliss-forge-api
│   ├── collaborator-snapshots/       # Safe copies for external developers
│   │   ├── a360-genai-platform-develop/  # Clean snapshot (no .git, no secrets)
│   │   ├── a360-web-app-develop/         # Clean snapshot
│   │   └── COLLABORATOR_README.md
│   ├── database-snapshots/           # Database exports for collaborators
│   │   ├── latest/                   # Junction to most recent snapshot
│   │   └── collaborator-snapshot-[timestamp]/
│   ├── scripts/                      # Sync and management scripts
│   └── docs/                         # Project documentation
└── [other-projects]/
```

## 🔄 Development Workflows

### Core Team Workflow (You)

```bash
# Navigate to base project
cd C:\Users\Chris\b360\your-base-project

# Develop directly in production repositories
cd production-repos/a360-web-app-develop
# Make changes - these are live in production repo

cd ../a360-genai-platform-develop  
# Make changes - these are live in production repo

# Commit changes to B360 environment
git add . && git commit -m "Feature implementation"
git push  # Goes to B360 shared repository
```

### Collaborator Workflow

```bash
# Collaborator receives base project (without production access)
cd collaborator-snapshots/

# Import database schema
mysql -u user -p database < ../database-snapshots/latest/schema.sql

# Review code for understanding
cd a360-web-app-develop/  # This is a snapshot, not live repo
# Study the code structure and APIs

# Create separate repo for contributions
gh repo create my-contribution-repo
# Develop features based on snapshot understanding
```

## 🔄 Sync Operations

### When to Sync Collaborator Snapshots

1. **Before Onboarding**: New collaborator joining
2. **Major Updates**: Significant changes to codebase
3. **API Changes**: When external interfaces change
4. **Weekly Cadence**: If active collaboration is ongoing

### Sync Commands

```powershell
# Update all collaborator snapshots
.\scripts\sync-snapshots.ps1

# Update specific repository
.\scripts\sync-snapshots.ps1 -Repositories @("a360-web-app-develop")

# Create database snapshot
.\scripts\create-db-snapshot.ps1

# Create database snapshot with sample data
.\scripts\create-db-snapshot.ps1 -IncludeData
```

## 📊 Database Strategy

### Reference Database (Development)
- **Location**: `https://pma.nextnlp.com/`
- **Access**: Warp environment (core team only)
- **Usage**: Real-time development and testing
- **Data**: Live development data
- **⚠️ Critical**: NOT available in production

### Snapshot Database (Collaborators)
- **Location**: `database-snapshots/latest/`
- **Access**: All collaborators
- **Usage**: Local development and testing  
- **Data**: Schema + sanitized sample data
- **Security**: No sensitive data, no production credentials

## 🔐 Security Model

### Core Team Access
- ✅ Direct access to production repositories via symlinks
- ✅ Real-time database access via Warp
- ✅ Full development environment
- ✅ Commit access to B360 shared environment

### Collaborator Access
- ✅ Read-only snapshots of code repositories
- ✅ Database schema and sample data
- ✅ Complete API documentation
- ✅ Development environment setup guides
- 🔒 No direct production repository access
- 🔒 No production database credentials
- 🔒 No sensitive configuration files

### Automatic Security Measures
- **Snapshot Cleaning**: Removes `.env`, `.key`, `.pem`, `secrets.*` files
- **Git History Removal**: No `.git` directories in snapshots
- **Credential Scrubbing**: Production credentials excluded
- **Data Sanitization**: Sample data scrubbed of sensitive information

## 🚀 Creation Commands

### Create New Base Project

```powershell
# Basic production mirror base project
.\scripts\new-base-project.ps1 -Name "a360-integration-base"

# Include PageCraft API and create GitHub repo
.\scripts\new-base-project.ps1 -Name "a360-full-base" -IncludePageCraft -CreateGitHub

# Run as administrator for symbolic links (recommended)
.\scripts\new-base-project.ps1 -Name "a360-base" -RunAsAdmin
```

### With PowerShell Profile Functions

```powershell
# After adding functions to your profile
nbp "a360-integration-base"                    # Basic base project
nbp "a360-full-base" -IncludePageCraft         # With PageCraft API  
nbp "a360-base" -CreateGitHub -RunAsAdmin      # Full featured
```

## 🛠️ Benefits of This Architecture

### For Core Development
1. **Real-time Integration**: Changes reflect immediately across ecosystem
2. **Production Mirroring**: Develop as if in production environment
3. **No Context Switching**: Direct access to all production repositories
4. **Commit to B360**: All work flows into shared environment

### For Collaboration  
1. **Realistic Environment**: Collaborators work with production-like setup
2. **Safe Development**: No risk of breaking production systems
3. **Complete Context**: Full codebase snapshots for understanding
4. **Easy Onboarding**: Self-contained development environment

### For Project Management
1. **Centralized in B360**: All projects in one shared location
2. **Version Controlled**: Base project structure tracked in Git
3. **Automated Sync**: Scripts handle snapshot updates
4. **Flexible Sharing**: Easy to control what collaborators access

## 📋 Best Practices

### Development Best Practices
1. **Test in Production Repos**: Use direct symlinked repositories for development
2. **Sync Before Sharing**: Always update snapshots before onboarding collaborators
3. **Document Changes**: Keep API and architecture documentation current
4. **Regular Snapshots**: Create database snapshots when schema changes

### Collaboration Best Practices
1. **Clear Communication**: Explain snapshot vs production distinction
2. **Regular Updates**: Sync snapshots during active collaboration
3. **Contribution Guidelines**: Define how collaborators submit work
4. **Security Reviews**: Regularly audit snapshot contents for sensitive data

### Maintenance Best Practices
1. **Monitor Symlinks**: Ensure symbolic links remain valid
2. **Clean Snapshots**: Verify sensitive files are excluded
3. **Database Hygiene**: Keep sample data current but sanitized
4. **Documentation Updates**: Maintain architecture and API docs

## 🔧 Troubleshooting

### Symlink Issues
```powershell
# If symlinks fail (need admin privileges)
# Script automatically creates directory references instead
# Development can continue, but requires manual sync
```

### Repository Path Changes
```powershell
# Update paths in create-production-mirror-base.ps1
# Re-run setup script to update symlinks
```

### Database Connection Issues
```powershell
# Verify Warp environment is active
# Check network connectivity to pma.nextnlp.com
# Create fresh database snapshot if needed
```

## 🎯 Integration with Existing Workflows

This architecture integrates seamlessly with:
- **Your existing A360 repositories**
- **B360 shared development environment**  
- **Warp database access**
- **GitHub collaboration workflows**
- **Your internal web publishing tools**

The production mirror base project becomes the foundation for all collaborative development while preserving your direct access to production systems.

---

*This architecture enables true production-mirrored development with safe collaboration capabilities.*