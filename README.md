# B360 - Monorepo

This repository contains both the iOS and web applications for the B360 project, plus the **Project Template** system.

## Repository Structure

- **`ios-app/`** - iOS Swift application (A360Scribe)
- **`web-app/`** - Web TypeScript/React application
- **`project-template/`** - Collaborative Development Project Template System

## Project Template System

> **Collaborative Development Project Template**

A comprehensive project template designed for collaborative development with GitHub integration, database connectivity, and external contributor support.

### Quick Start for Project Template

```bash
# Navigate to the project template
cd project-template

# Create a new collaborative project
.\scripts\create-new-project.ps1 -ProjectName "my-project" -ProjectPath "C:\Users\Chris\Projects" -InitializeGit

# Create a project with PageCraft integration
.\scripts\create-new-project.ps1 -ProjectName "pagecraft-project" -IncludePageCraftAccess -InitializeGit
```

### Template Features
- ✅ **GitHub Integration** - Automated repository creation and configuration
- ✅ **Database Support** - Reference database for development + production schema documentation
- ✅ **Multi-Language** - Node.js/Express or Python/FastAPI support
- ✅ **PageCraft Integration** - Optional web publishing and content management
- ✅ **Production Mirror** - Create base projects that mirror production repositories
- ✅ **Collaboration-Ready** - Public documentation for external contributors, private core code

## Getting Started

### iOS App
```bash
cd ios-app
# Open A360Scribe.xcodeproj in Xcode
```

### Web App
```bash
cd web-app
npm install
npm start
```

### Project Template
```bash
cd project-template
# See WARP.md for complete documentation
# See TEMPLATE-USAGE.md for usage guide
```

## Development

Both applications can be developed independently within their respective directories. The project template provides automation for creating new collaborative projects.

## Documentation

- **Project Template**: See `project-template/WARP.md` for complete development commands and architecture
- **Template Usage**: See `project-template/TEMPLATE-USAGE.md` for project creation guide
- **PageCraft Integration**: See `project-template/docs/pagecraft-integration.md` for web publishing setup

---

**Note**: The project template includes reference database access for development that will not be available in production environments.
