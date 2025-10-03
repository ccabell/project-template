# PageCraft Integration Documentation

## Overview

This project can optionally integrate with the **page-craft-bliss-forge-api** system to provide content management and web publishing capabilities. This integration allows projects to:

- Publish project documentation to the web with password protection
- Create and manage content for project websites
- Integrate with workflow publishing systems
- Share specific project content with collaborators

## Integration Features

### Content Management
- **Project Documentation**: Automatically publish README, API docs, and project guides
- **Dynamic Content**: Create and update web content programmatically
- **Template System**: Use predefined templates for consistent project presentation
- **Version Control**: Track content versions and changes

### Publishing Workflow
- **Password Protection**: Secure main page access for sensitive projects
- **Selective Sharing**: Share specific content with external collaborators
- **Staging Environment**: Test content before publishing to production
- **Automated Publishing**: Integrate with CI/CD for automatic content updates

### Access Management
- **User Creation**: Create test users for specific project access
- **Permission Control**: Grant read, write, or publish permissions
- **Project Isolation**: Control what content each user can access
- **Authentication**: Secure API-based authentication system

## Configuration

### Environment Variables

When PageCraft integration is enabled, configure these environment variables:

```bash
# PageCraft API Configuration
PAGECRAFT_ENABLED=true
PAGECRAFT_API_URL=http://localhost:8080/api
PAGECRAFT_API_KEY=your_pagecraft_api_key

# Publishing URLs
PAGECRAFT_STAGING_URL=https://staging.pagecraft.com
PAGECRAFT_PRODUCTION_URL=https://pagecraft.com

# Project Configuration
PAGECRAFT_PROJECT_ID=your_project_id
```

### Configuration File

The `config/pagecraft.json` file contains detailed integration settings:

```json
{
  "pagecraft": {
    "enabled": true,
    "api_base_url": "${PAGECRAFT_API_URL}",
    "api_key": "${PAGECRAFT_API_KEY}",
    "integration_type": "full"
  },
  "endpoints": {
    "content": "/api/pagecraft/content",
    "templates": "/api/pagecraft/templates", 
    "publish": "/api/pagecraft/publish",
    "projects": "/api/pagecraft/projects"
  },
  "permissions": {
    "read": true,
    "write": true,
    "publish": true,
    "create_projects": true
  }
}
```

## API Endpoints

### Content Management

#### Create Content
```http
POST /api/pagecraft/content
Authorization: Bearer <pagecraft_token>
Content-Type: application/json

{
  "title": "Project Documentation",
  "content": "# Project Overview\n\nThis is the main project documentation...",
  "type": "markdown",
  "project_id": "your_project_id",
  "publish": false
}
```

#### Update Content
```http
PUT /api/pagecraft/content/{content_id}
Authorization: Bearer <pagecraft_token>
Content-Type: application/json

{
  "title": "Updated Documentation",
  "content": "# Updated Project Overview\n\nThis documentation has been updated...",
  "publish": true
}
```

#### Get Content
```http
GET /api/pagecraft/content/{content_id}
Authorization: Bearer <pagecraft_token>
```

### Publishing

#### Publish Content
```http
POST /api/pagecraft/publish
Authorization: Bearer <pagecraft_token>
Content-Type: application/json

{
  "content_ids": ["content_1", "content_2"],
  "environment": "staging",
  "notify_users": true
}
```

#### Get Project Status
```http
GET /api/pagecraft/projects/{project_id}/status
Authorization: Bearer <pagecraft_token>
```

### User Management

#### Create Test User
```http
POST /api/pagecraft/users
Authorization: Bearer <pagecraft_token>
Content-Type: application/json

{
  "username": "test_collaborator",
  "email": "collaborator@example.com",
  "permissions": ["read"],
  "project_access": ["your_project_id"],
  "temporary": true,
  "expires_in": "30d"
}
```

## Integration Examples

### Node.js Integration

```javascript
const express = require('express');
const { PageCraftClient } = require('./lib/pagecraft-client');

const app = express();
const pagecraft = new PageCraftClient({
  apiUrl: process.env.PAGECRAFT_API_URL,
  apiKey: process.env.PAGECRAFT_API_KEY,
  projectId: process.env.PAGECRAFT_PROJECT_ID
});

// Publish documentation endpoint
app.post('/publish-docs', async (req, res) => {
  try {
    const result = await pagecraft.publishContent({
      title: 'API Documentation',
      content: req.body.documentation,
      type: 'markdown'
    });
    
    res.json({ success: true, url: result.published_url });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});
```

### Python Integration

```python
import os
import requests
from typing import Dict, Any

class PageCraftClient:
    def __init__(self):
        self.api_url = os.getenv('PAGECRAFT_API_URL')
        self.api_key = os.getenv('PAGECRAFT_API_KEY')
        self.project_id = os.getenv('PAGECRAFT_PROJECT_ID')
        
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def publish_content(self, title: str, content: str, content_type: str = 'markdown') -> Dict[str, Any]:
        """Publish content to PageCraft system"""
        data = {
            'title': title,
            'content': content,
            'type': content_type,
            'project_id': self.project_id,
            'publish': True
        }
        
        response = requests.post(
            f'{self.api_url}/content',
            json=data,
            headers=self.headers
        )
        
        return response.json()

# FastAPI endpoint example
from fastapi import FastAPI

app = FastAPI()
pagecraft = PageCraftClient()

@app.post('/publish-docs')
async def publish_documentation(documentation: str):
    result = pagecraft.publish_content(
        title='Project Documentation',
        content=documentation
    )
    return {'success': True, 'url': result.get('published_url')}
```

## Security Considerations

### Authentication
- All API calls require valid PageCraft API key
- API keys should be stored in environment variables, never in code
- Use temporary tokens for test users and collaborators

### Access Control
- Configure appropriate permissions for each user type
- Use project-level isolation to control content access
- Regularly review and rotate API keys

### Content Security
- Validate all content before publishing
- Sanitize user-generated content to prevent XSS
- Use HTTPS for all API communications
- Enable CORS only for trusted domains

## Collaboration Workflow

### For External Collaborators

1. **Access Request**: Contact project maintainer for PageCraft access
2. **Test Account**: Receive temporary test user credentials
3. **Content Review**: Access project content through PageCraft interface
4. **Feedback Submission**: Submit feedback through PageCraft comment system
5. **Content Updates**: View updated content as project evolves

### For Core Team

1. **Content Creation**: Create and edit content through API or interface
2. **Review Process**: Use staging environment for content review
3. **Publishing**: Publish approved content to production
4. **User Management**: Create and manage test user accounts
5. **Analytics**: Monitor content access and engagement

## Troubleshooting

### Common Issues

**API Authentication Fails**
- Verify `PAGECRAFT_API_KEY` is set correctly
- Check API key hasn't expired
- Ensure API key has correct permissions

**Content Not Publishing**
- Check project permissions in PageCraft system
- Verify content passes validation rules
- Ensure staging environment is accessible

**User Access Issues**
- Verify user has been granted project access
- Check user account hasn't expired
- Confirm user is accessing correct project URL

### Support

For PageCraft integration issues:
- Check PageCraft API documentation
- Verify configuration in `config/pagecraft.json`
- Test API connectivity with health check endpoint
- Contact PageCraft system administrator for access issues

## Best Practices

### Content Management
- Use meaningful titles and descriptions for all content
- Implement content versioning for important documents
- Regular backup published content
- Use templates for consistent formatting

### User Management
- Create time-limited accounts for external collaborators
- Use principle of least privilege for permissions
- Regular audit of user access and permissions
- Remove unused accounts promptly

### Integration Development
- Implement proper error handling for API calls
- Use environment-specific configuration
- Test integration in staging before production
- Monitor API usage and rate limits

---

**Note**: PageCraft integration is optional and designed to work independently of the main project functionality. Projects should function normally even if PageCraft services are unavailable.