# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a **Collaborative Project Template** designed for creating new projects with GitHub integration, database connectivity, and external collaboration support while keeping core code private. The template supports both Node.js/Express and Python/FastAPI projects and integrates with the B360 shared development environment.

## Key Architecture Components

### Template Structure
- **Collaboration-First Design**: Public API/infrastructure docs for external contributors, private core code
- **Multi-Language Support**: Configurable Node.js or Python project generation
- **Database Strategy**: Reference database for development (pma.nextnlp.com) + production database documentation
- **B360 Integration**: Designed to work within the B360 shared repository environment
- **Production Mirror Architecture**: Supports creating base projects that mirror production repositories with safe collaborator snapshots

### Core Directories
- `scripts/` - PowerShell automation scripts for project creation and management
- `docs/` - Template documentation (API, database schema, infrastructure) for external collaborators
- `config/` - Database configuration templates with environment-based setup
- `database/` - Internal database reference documentation (development only)

## Common Development Commands

### Project Creation
```powershell
# Create a basic collaborative project (Node.js)
.\scripts\create-new-project.ps1 -ProjectName "my-project" -ProjectPath "C:\Users\Chris\Projects" -InitializeGit

# Create a Python project with GitHub integration
.\scripts\create-new-project.ps1 -ProjectName "api-service" -ProjectPath "C:\Users\Chris\Projects" -Python -InitializeGit -CreateGitHubRepo -GitHubUsername "your-username"

# Create project with PageCraft integration
.\scripts\create-new-project.ps1 -ProjectName "pagecraft-project" -ProjectPath "C:\Users\Chris\Projects" -IncludePageCraftAccess -InitializeGit

# Create a production mirror base project with PageCraft
.\scripts\create-production-mirror-base.ps1 -BaseProjectName "a360-integration-base" -IncludePageCraft

# Create A360-specific project
.\scripts\create-a360-project.ps1 -ProjectName "my-a360-project" -ProjectType "api"

# Create base project directly from new project script
.\scripts\create-new-project.ps1 -ProjectName "base-project" -ProjectPath "C:\Users\Chris\b360" -CreateBaseProject -IncludePageCraftAccess
```

### Generated Project Commands
For **Node.js** projects created by this template:
```bash
# Setup and development
npm run setup        # Install dependencies and copy .env.example to .env
npm run dev          # Start development server with nodemon
npm test             # Run Jest tests
npm run test:watch   # Run tests in watch mode
npm run lint         # Run ESLint
npm run lint:fix     # Fix ESLint issues automatically
npm run build        # Lint and test (CI preparation)
```

For **Python** projects created by this template:
```bash
# Setup and development
pip install -r requirements.txt
python -m uvicorn src.main:app --reload  # Start development server
pytest                                   # Run tests
pytest --watch                          # Run tests in watch mode
black src/                              # Format code
flake8 src/                             # Lint code
mypy src/                               # Type checking
```

### Template Management
```powershell
# Sync production repositories to collaborator snapshots (for base projects)
.\scripts\sync-snapshots.ps1

# Advanced sync with watch mode for active development
.\scripts\sync-for-active-development.ps1 -WatchMode -CheckIntervalMinutes 30

# Setup GitHub integration for existing project
.\scripts\setup-github.ps1 -ProjectName "project-name" -GitHubUsername "username" -CreateRepo
```

## Database Architecture

### Development Reference Database
- **URL**: `https://pma.nextnlp.com/` (phpMyAdmin interface)
- **Access**: Via Warp environment (credentials managed through Warp)
- **Purpose**: Sample data and schema reference for development
- **⚠️ CRITICAL**: This database is **DEVELOPMENT ONLY** and will **NOT** be available in production

### Database Configuration Pattern
Projects use environment-based configuration:
- **Development**: Local database + reference database access
- **Production**: Separate secure production database
- **Testing**: Local test database instance

Configuration managed through `.env` files and `config/database.json`.

## PowerShell Profile Integration

Add these functions to your PowerShell profile for quick access:
```powershell
# Quick project creation aliases
ncp "project-name"                    # New-CollaborativeProject
na360 "project-name" -Type "api"      # New-A360Project  
nbp "base-name"                       # New-BaseProject
goa360                               # Go-A360 (navigate to B360)
got                                  # Go-Template (navigate to template)
```

Full PowerShell profile additions available in `scripts/powershell-profile-addition.ps1`.

## Production Mirror Architecture

This template supports creating "base projects" that provide:
1. **Direct Development Access**: Symbolic links to production repositories for core team
2. **Safe Collaboration**: Clean snapshots for external contributors
3. **B360 Integration**: Projects live in B360 shared environment
4. **Automated Sync**: Scripts to update collaborator snapshots from production repositories

### Base Project Structure
```
base-project/
├── production-repos/           # Symlinks to actual production repos (core team)
├── collaborator-snapshots/     # Clean copies for external contributors
├── database-snapshots/         # Database exports for collaborators
└── scripts/                    # Sync and management automation
```

## Security Model

### What External Collaborators Access
- Complete API documentation and database schema
- Clean code snapshots (no `.git`, `.env`, secrets)
- Development environment setup guides
- Sample/sanitized database data

### What Remains Private
- Direct production repository access
- Production database credentials
- Environment-specific configuration files
- Live development database access

## Environment Variables

Key environment variables used across projects:
```bash
# Database (Development)
REF_DB_HOST=pma.nextnlp.com    # Reference database (dev only)
DB_USERNAME=your_local_db_user  # Local development database
DB_PASSWORD=your_local_db_password

# Database (Production) 
PROD_DB_HOST=${SECURE_HOST}
PROD_DB_USERNAME=${SECURE_USERNAME}
PROD_DB_PASSWORD=${SECURE_PASSWORD}

# Application
NODE_ENV=development|production
PORT=3000|8000
JWT_SECRET=${JWT_SECRET}
API_KEY=${API_KEY}

# PageCraft Integration (when enabled)
PAGECRAFT_API_URL=http://localhost:8080/api
PAGECRAFT_API_KEY=your_pagecraft_api_key
PAGECRAFT_ENABLED=true
```

## Integration Points

### Warp Integration
- Reference database access managed through Warp environment
- Project template integrates with Warp's project tracking capabilities
- Database credentials automatically available in Warp context

### GitHub Integration
- Automated repository creation with proper collaboration setup
- Issue templates and branch protection
- Integration with B360 shared development workflow

### B360 Ecosystem Integration
The template works with:
- `a360-genai-platform-develop` (core GenAI platform)
- `a360-web-app-develop` (web application)  
- `a360-data-lake` (data lake repository)
- `a360-data-science` (data science and MLOps)
- `page-craft-bliss-forge-api` (optional integration for content management and publishing)

### PageCraft Integration
When `-IncludePageCraftAccess` is specified:
- Creates `config/pagecraft.json` with API endpoint configuration
- Adds PageCraft environment variables to `.env.example`
- Provides integration with the page-craft-bliss-forge-api system
- Enables content management and publishing capabilities
- Supports web publishing workflows for project documentation and content

## Testing Strategy

### Node.js Testing
- **Framework**: Jest with Supertest for API testing
- **Structure**: Tests in `tests/` directory
- **Commands**: `npm test` for single run, `npm run test:watch` for development

### Python Testing  
- **Framework**: pytest with pytest-asyncio for async testing
- **Structure**: Tests in `tests/` directory
- **Commands**: `pytest` for single run, `pytest --watch` for development

### Database Testing
- Separate test database configuration
- Sample data fixtures available through reference database
- Migration testing through database snapshots

## Collaboration Workflow

1. **Core Team**: Work directly in production repositories via symlinks
2. **External Contributors**: Work with clean snapshots, submit contributions via separate repositories
3. **Documentation**: All API changes must update documentation in `docs/`
4. **Database Changes**: Schema changes require updates to both development and production documentation
5. **Sync Process**: Use sync scripts to update collaborator snapshots when production changes

## Important Notes

### Database Warning
Always remind users that the reference database (`pma.nextnlp.com`) is **development-only**:
- Any functionality depending on this data must include supporting data exports for production
- Production applications must work independently of the reference database
- All database-dependent features need proper production database configuration

### Security Considerations
- Never commit secrets to repositories created from this template
- All sensitive configuration must use environment variables
- Production credentials are managed separately from development credentials
- Collaborator snapshots are automatically cleaned of sensitive files

### Version Control Integration
- Template supports both local Git initialization and automated GitHub repository creation
- B360 shared environment commits flow through the B360 repository structure
- Production repositories maintain their own version control while snapshots are Git-free for collaborators

## Troubleshooting

### Symlink Issues
If symbolic link creation fails (requires admin privileges), scripts automatically create directory references with manual sync instructions.

### Database Connection Issues  
- Verify Warp environment is active for reference database access
- Check network connectivity to `pma.nextnlp.com`
- Ensure local database is running for development

### Repository Path Issues
Update repository paths in `create-production-mirror-base.ps1` if production repositories move locations.

<citations>
<document>
    <document_type>RULE</document_type>
    <document_id>1A00KqHhrUaLQB5e20ZkBJ</document_id>
</document>
<document>
    <document_type>RULE</document_type>
    <document_id>wBStHKfrilJDcBE8YAoO61</document_id>
</document>
</citations>