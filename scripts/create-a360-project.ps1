# A360 Ecosystem Project Creator
# Specialized script for creating projects that integrate with A360 platform

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectName,
    
    [Parameter(Mandatory=$false)]
    [string]$ProjectDescription = "A360 ecosystem integration project",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("api", "web", "integration", "microservice")]
    [string]$ProjectType = "api",
    
    [Parameter(Mandatory=$false)]
    [switch]$Python,
    
    [Parameter(Mandatory=$false)]
    [switch]$NodeJS,
    
    [Parameter(Mandatory=$false)]
    [switch]$CreateGitHubRepo
)

# A360 project paths
$A360BasePath = "C:\Users\Chris\b360"
$ProjectPath = $A360BasePath

Write-Host "Creating A360 ecosystem project: $ProjectName" -ForegroundColor Green
Write-Host "Project type: $ProjectType" -ForegroundColor Cyan
Write-Host "Location: $ProjectPath" -ForegroundColor Cyan

# Determine language based on project type if not specified
if (-not $Python -and -not $NodeJS) {
    switch ($ProjectType) {
        "api" { $Python = $true }
        "web" { $NodeJS = $true }
        "integration" { $Python = $true }
        "microservice" { $NodeJS = $true }
        default { $NodeJS = $true }
    }
}

# Create the base project using the main template
$templateScript = "$PSScriptRoot\create-new-project.ps1"
$params = @{
    ProjectName = $ProjectName
    ProjectPath = $ProjectPath
    ProjectDescription = $ProjectDescription
    AuthorName = "Chris"
    GitHubUsername = "ccabell"
    InitializeGit = $true
}

if ($Python) { $params.Python = $true }
if ($NodeJS) { $params.NodeJS = $true }
if ($CreateGitHubRepo) { $params.CreateGitHubRepo = $true }

& $templateScript @params

$newProjectPath = Join-Path $ProjectPath $ProjectName

# A360-specific customizations
Write-Host "Adding A360-specific customizations..." -ForegroundColor Yellow

# Update the README with A360-specific information
$a360ReadmeAddition = @"

## A360 Ecosystem Integration

This project is part of the A360 platform ecosystem and integrates with:

### Core A360 Repositories
- **Web App**: `C:\Users\Chris\b360\web-app` - Main A360 web application
- **Platform Development**: A360 GenAI platform components
- **Reference Database**: Available via Warp environment (development only)

### Integration Points
- **Database**: Connects to A360 reference database for development
- **API Endpoints**: Designed to work with A360 platform APIs  
- **Authentication**: Compatible with A360 authentication system
- **Data Models**: Follows A360 data structure patterns

### Development Workflow
1. **Reference Data**: Use Warp database access for development
2. **Local Testing**: Test against A360 web app running locally
3. **API Integration**: Ensure compatibility with existing A360 endpoints
4. **Documentation**: Update A360 ecosystem documentation

### Deployment Considerations
- **Production Database**: Uses separate production database (not reference DB)
- **Environment Variables**: Configure for A360 production environment
- **Load Balancing**: Consider integration with A360 infrastructure
- **Security**: Follow A360 security protocols

### Related Documents
- A360 Architecture Analysis
- Integration Strategy Documents
- Platform Development Guidelines

---
*Generated from A360 Project Template*
"@

# Append A360-specific content to README
Add-Content "$newProjectPath\README.md" $a360ReadmeAddition

# Create A360-specific environment variables
$a360EnvAddition = @"

# A360 Ecosystem Configuration
A360_WEB_APP_URL=http://localhost:3000
A360_API_BASE_URL=http://localhost:8000/api
A360_PLATFORM_ENV=development

# A360 Database Integration
A360_DB_SYNC_ENABLED=true
A360_REFERENCE_DB_ACCESS=true

# A360 Authentication
A360_AUTH_PROVIDER=internal
A360_JWT_SECRET=your_a360_jwt_secret

# A360 Integration Services
ZENOTI_INTEGRATION_ENABLED=false
MEDPLUM_INTEGRATION_ENABLED=false
KERAGON_INTEGRATION_ENABLED=false
"@

Add-Content "$newProjectPath\.env.example" $a360EnvAddition

# Update project.json with A360-specific metadata
$projectJsonPath = "$newProjectPath\project.json"
$projectConfig = Get-Content $projectJsonPath | ConvertFrom-Json
$projectConfig.project | Add-Member -NotePropertyName "ecosystem" -NotePropertyValue "A360"
$projectConfig.project | Add-Member -NotePropertyName "integration_type" -NotePropertyValue $ProjectType
$projectConfig.project | Add-Member -NotePropertyName "base_path" -NotePropertyValue $A360BasePath

$projectConfig | ConvertTo-Json -Depth 10 | Set-Content $projectJsonPath

# Create A360-specific documentation
$a360DocsPath = "$newProjectPath\docs\a360-integration.md"
@"
# A360 Ecosystem Integration Guide

## Overview

This project integrates with the A360 platform ecosystem, providing specialized functionality while maintaining compatibility with existing A360 infrastructure.

## A360 Platform Components

### Core Repositories
- **A360 Web App**: Main user interface and web application
- **A360 GenAI Platform**: AI/ML platform development components  
- **Integration Services**: Various integration points (Zenoti, Medplum, Keragon)

### Database Integration
- **Development**: Uses A360 reference database via Warp
- **Production**: Separate secure database following A360 patterns
- **Synchronization**: Compatible with A360 data sync mechanisms

## Integration Architecture

### API Integration
```
A360 Web App <-> This Service <-> A360 Database
     ^                ^                ^
     |                |                |
A360 Platform <-> Integration APIs <-> External Services
```

### Data Flow
1. **Inbound**: Receives data from A360 web app and platform
2. **Processing**: Applies business logic following A360 patterns  
3. **Outbound**: Integrates with external services and databases
4. **Sync**: Maintains data consistency with A360 ecosystem

## Development Integration

### Local Development
1. **A360 Web App**: Run locally on port 3000
2. **This Service**: Run on designated port
3. **Database**: Connect to A360 reference database via Warp
4. **Testing**: Coordinate with A360 platform components

### Environment Setup
```bash
# Start A360 web app
cd C:\Users\Chris\b360\web-app
npm run dev

# Start this service
cd C:\Users\Chris\b360\$ProjectName
npm run dev  # or python -m uvicorn main:app --reload
```

## Production Deployment

### Integration Points
- **Load Balancer**: Integrate with A360 load balancing
- **Database**: Connect to A360 production database infrastructure
- **Authentication**: Use A360 authentication system
- **Monitoring**: Integrate with A360 monitoring and logging

### Configuration Management
- Environment variables managed through A360 configuration system
- Secrets stored in A360 secure vault
- Feature flags coordinated with A360 platform

## Testing Strategy

### Integration Testing
- Test against A360 web app locally
- Validate database compatibility
- Verify API endpoint integration
- Test authentication flows

### End-to-End Testing
- Full A360 ecosystem testing
- External service integration testing
- Production-like environment testing

## Maintenance and Updates

### Version Compatibility
- Track A360 platform version compatibility
- Update integration points as needed
- Maintain backward compatibility when possible

### Documentation Updates
- Keep API documentation in sync with A360 platform
- Update integration guides as ecosystem evolves
- Coordinate changes with A360 team

---

*This integration guide is specific to the A360 ecosystem and should be updated as the platform evolves.*
"@ | Set-Content $a360DocsPath

Write-Host "`nA360 project created successfully!" -ForegroundColor Green
Write-Host "Project location: $newProjectPath" -ForegroundColor Cyan
Write-Host "A360 ecosystem integration configured!" -ForegroundColor Green

Write-Host "`nA360-specific features added:" -ForegroundColor Yellow
Write-Host "- A360 ecosystem README section" -ForegroundColor White
Write-Host "- A360 environment variables" -ForegroundColor White
Write-Host "- A360 integration documentation" -ForegroundColor White
Write-Host "- A360 project metadata" -ForegroundColor White

Write-Host "`nNext steps for A360 integration:" -ForegroundColor Cyan
Write-Host "1. Review docs/a360-integration.md" -ForegroundColor White
Write-Host "2. Configure A360-specific environment variables" -ForegroundColor White
Write-Host "3. Test integration with A360 web app" -ForegroundColor White
Write-Host "4. Set up database connection via Warp" -ForegroundColor White