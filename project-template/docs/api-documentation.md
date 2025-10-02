# API Documentation

## Overview

This document provides complete API reference for external collaborators. All endpoints documented here are stable and production-ready.

**Base URL**: `https://api.yourproject.com/api`
**Development URL**: `http://localhost:3000/api`

## Authentication

### Authentication Header
```
Authorization: Bearer <your_token>
```

### Get Authentication Token
```http
POST /auth/login
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**Response:**
```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "username": "your_username",
    "role": "user"
  }
}
```

## Core Endpoints

### Health Check
Check API status and connectivity.

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-02T17:46:02Z",
  "version": "1.0.0",
  "database": "connected"
}
```

### Data Retrieval

#### Get All Records
```http
GET /data
Authorization: Bearer <token>
```

**Query Parameters:**
- `page` (integer, optional): Page number (default: 1)
- `limit` (integer, optional): Records per page (default: 20, max: 100)
- `sort` (string, optional): Sort field (default: 'created_at')
- `order` (string, optional): Sort order 'asc' or 'desc' (default: 'desc')
- `search` (string, optional): Search query
- `filter` (string, optional): Filter criteria

**Example:**
```http
GET /data?page=1&limit=10&sort=name&order=asc&search=example
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "Example Record",
      "description": "Sample data",
      "status": "active",
      "created_at": "2025-10-02T17:46:02Z",
      "updated_at": "2025-10-02T17:46:02Z"
    }
  ],
  "pagination": {
    "current_page": 1,
    "per_page": 10,
    "total": 25,
    "total_pages": 3
  }
}
```

#### Get Single Record
```http
GET /data/{id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "Example Record",
    "description": "Sample data",
    "status": "active",
    "metadata": {
      "tags": ["example", "demo"],
      "category": "sample"
    },
    "created_at": "2025-10-02T17:46:02Z",
    "updated_at": "2025-10-02T17:46:02Z"
  }
}
```

#### Create New Record
```http
POST /data
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "New Record",
  "description": "Description of new record",
  "status": "active",
  "metadata": {
    "tags": ["new", "record"],
    "category": "user-generated"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Record created successfully",
  "data": {
    "id": 26,
    "name": "New Record",
    "description": "Description of new record",
    "status": "active",
    "metadata": {
      "tags": ["new", "record"],
      "category": "user-generated"
    },
    "created_at": "2025-10-02T17:46:02Z",
    "updated_at": "2025-10-02T17:46:02Z"
  }
}
```

#### Update Record
```http
PUT /data/{id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Updated Record Name",
  "description": "Updated description",
  "status": "inactive"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Record updated successfully",
  "data": {
    "id": 1,
    "name": "Updated Record Name",
    "description": "Updated description",
    "status": "inactive",
    "created_at": "2025-10-02T17:46:02Z",
    "updated_at": "2025-10-02T17:50:02Z"
  }
}
```

#### Delete Record
```http
DELETE /data/{id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "message": "Record deleted successfully"
}
```

## Error Handling

### Error Response Format
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": "Additional error details"
  },
  "timestamp": "2025-10-02T17:46:02Z"
}
```

### Common Error Codes
- `400` - Bad Request: Invalid request data
- `401` - Unauthorized: Missing or invalid authentication
- `403` - Forbidden: Insufficient permissions
- `404` - Not Found: Resource not found
- `422` - Unprocessable Entity: Validation errors
- `429` - Too Many Requests: Rate limit exceeded
- `500` - Internal Server Error: Server error

### Validation Error Example
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": {
      "name": ["Name is required"],
      "email": ["Invalid email format"]
    }
  }
}
```

## Rate Limiting

- **Rate Limit**: 100 requests per minute per user
- **Headers**: 
  - `X-RateLimit-Limit`: Request limit per window
  - `X-RateLimit-Remaining`: Requests remaining in current window
  - `X-RateLimit-Reset`: Time when the rate limit resets

## Data Types and Validation

### Common Field Types
- `id`: Integer, auto-generated
- `name`: String, required, max 255 characters
- `description`: String, optional, max 1000 characters
- `status`: Enum ['active', 'inactive', 'pending', 'archived']
- `created_at`: DateTime, ISO 8601 format
- `updated_at`: DateTime, ISO 8601 format
- `metadata`: Object, flexible JSON structure

### Required Fields
- `name`: Always required for POST requests
- `status`: Defaults to 'active' if not provided

### Optional Fields
- `description`: Can be null or empty
- `metadata`: Flexible object for additional data

## Testing

### Test Environment
- Base URL: `https://api-test.yourproject.com/api`
- Test credentials available upon request

### Sample cURL Commands
```bash
# Health check
curl -X GET https://api.yourproject.com/api/health

# Get data with authentication
curl -X GET https://api.yourproject.com/api/data \
  -H "Authorization: Bearer YOUR_TOKEN"

# Create new record
curl -X POST https://api.yourproject.com/api/data \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Record", "description": "Test description"}'
```

## Webhooks (Future)

*Webhook functionality is planned for future releases*

## Contact & Support

For API support or questions:
- Create GitHub issue with 'api' label
- Include API endpoint, request/response, and error details
- Provide reproduction steps

## Changelog

### Version 1.0.0 (2025-10-02)
- Initial API release
- Core CRUD operations
- Authentication system
- Rate limiting

---

**Note**: This API is designed to work independently of the reference development database. All production deployments use separate, secure database infrastructure.