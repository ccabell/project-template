# Database Schema Documentation

## Overview

This document describes the production database schema that external collaborators should use when developing against this project.

⚠️ **Important**: This schema represents the production database structure. The development reference database may contain additional tables or fields that are not available in production.

## Core Tables

### users
User account information and authentication data.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INT | PRIMARY KEY, AUTO_INCREMENT | Unique user identifier |
| username | VARCHAR(50) | UNIQUE, NOT NULL | User's login name |
| email | VARCHAR(255) | UNIQUE, NOT NULL | User's email address |
| password_hash | VARCHAR(255) | NOT NULL | Hashed password (bcrypt) |
| role | ENUM('user', 'admin', 'moderator') | DEFAULT 'user' | User role/permissions |
| status | ENUM('active', 'inactive', 'suspended') | DEFAULT 'active' | Account status |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Account creation time |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | Last update time |
| last_login | TIMESTAMP | NULL | Last login timestamp |

**Indexes:**
- PRIMARY KEY (id)
- UNIQUE KEY (username)
- UNIQUE KEY (email)
- KEY (status)

### data_records
Main data storage table for application records.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INT | PRIMARY KEY, AUTO_INCREMENT | Unique record identifier |
| name | VARCHAR(255) | NOT NULL | Record name/title |
| description | TEXT | NULL | Detailed description |
| status | ENUM('active', 'inactive', 'pending', 'archived') | DEFAULT 'active' | Record status |
| user_id | INT | FOREIGN KEY REFERENCES users(id) | Record owner |
| metadata | JSON | NULL | Flexible metadata storage |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | Last update timestamp |

**Indexes:**
- PRIMARY KEY (id)
- FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
- KEY (status)
- KEY (created_at)
- KEY (user_id, status)

### api_keys
API key management for authentication.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INT | PRIMARY KEY, AUTO_INCREMENT | Unique key identifier |
| key_hash | VARCHAR(255) | UNIQUE, NOT NULL | Hashed API key |
| user_id | INT | FOREIGN KEY REFERENCES users(id) | Key owner |
| name | VARCHAR(100) | NOT NULL | Key description/name |
| permissions | JSON | NULL | Key-specific permissions |
| expires_at | TIMESTAMP | NULL | Expiration timestamp |
| last_used | TIMESTAMP | NULL | Last usage timestamp |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| is_active | BOOLEAN | DEFAULT TRUE | Key status |

**Indexes:**
- PRIMARY KEY (id)
- UNIQUE KEY (key_hash)
- FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
- KEY (expires_at)
- KEY (is_active)

### audit_logs
System activity logging for security and debugging.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INT | PRIMARY KEY, AUTO_INCREMENT | Unique log identifier |
| user_id | INT | FOREIGN KEY REFERENCES users(id), NULL | User who performed action |
| action | VARCHAR(100) | NOT NULL | Action performed |
| table_name | VARCHAR(50) | NULL | Affected table |
| record_id | INT | NULL | Affected record ID |
| old_values | JSON | NULL | Previous values |
| new_values | JSON | NULL | New values |
| ip_address | VARCHAR(45) | NULL | Client IP address |
| user_agent | TEXT | NULL | Client user agent |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Action timestamp |

**Indexes:**
- PRIMARY KEY (id)
- FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
- KEY (action)
- KEY (table_name, record_id)
- KEY (created_at)
- KEY (user_id, created_at)

## Relationships

### User → Data Records (One-to-Many)
- Each user can have multiple data records
- Foreign key: `data_records.user_id` → `users.id`
- Cascade delete: When user is deleted, their records are deleted

### User → API Keys (One-to-Many)
- Each user can have multiple API keys
- Foreign key: `api_keys.user_id` → `users.id`
- Cascade delete: When user is deleted, their API keys are deleted

### User → Audit Logs (One-to-Many)
- Each user can have multiple audit log entries
- Foreign key: `audit_logs.user_id` → `users.id`
- Set NULL on delete: When user is deleted, logs remain but user_id becomes NULL

## Data Types

### JSON Fields
Both `data_records.metadata` and `api_keys.permissions` use JSON fields for flexible data storage.

**Example metadata structure:**
```json
{
  "tags": ["important", "project-alpha"],
  "category": "user-generated",
  "custom_fields": {
    "priority": "high",
    "department": "engineering"
  }
}
```

**Example permissions structure:**
```json
{
  "read": true,
  "write": true,
  "delete": false,
  "admin": false
}
```

### ENUM Values

**User roles:**
- `user`: Standard user access
- `admin`: Full system access
- `moderator`: Limited administrative access

**User status:**
- `active`: Normal active account
- `inactive`: Temporarily disabled
- `suspended`: Suspended due to violations

**Record status:**
- `active`: Normal active record
- `inactive`: Hidden/disabled record
- `pending`: Awaiting approval/processing
- `archived`: Archived for historical purposes

## Database Constraints

### NOT NULL Requirements
- All `id` fields (auto-generated)
- `users.username`, `users.email`, `users.password_hash`
- `data_records.name`
- `api_keys.key_hash`, `api_keys.name`
- `audit_logs.action`

### UNIQUE Constraints
- `users.username`
- `users.email`
- `api_keys.key_hash`

### Foreign Key Constraints
All foreign keys are properly defined with appropriate cascade/set null rules for data integrity.

## Performance Considerations

### Recommended Indexes
The schema includes indexes on commonly queried fields:
- Status fields for filtering
- Timestamp fields for sorting
- Foreign keys for joins
- Composite indexes for common query patterns

### Query Optimization
- Use `data_records.user_id` + `status` composite index for user-specific filtered queries
- Use `created_at` indexes for chronological sorting
- Consider adding indexes on JSON fields if querying metadata frequently

## Migration Strategy

When updating from development to production:

1. **Do not assume reference database tables exist**
2. **Always check for table existence before queries**
3. **Use migrations for schema changes**
4. **Test queries against this documented schema**

## Environment-Specific Notes

### Development
- May include additional tables for testing
- Reference database contains sample data
- Some fields may have different constraints

### Production
- Strict adherence to this schema
- All constraints enforced
- Full audit logging enabled
- Performance optimizations applied

## Security Considerations

### Sensitive Data
- Passwords are hashed using bcrypt
- API keys are stored as hashes
- IP addresses and user agents logged for security
- JSON fields should not contain sensitive information

### Access Control
- Use proper authentication before database queries
- Respect user role permissions
- Log all data access in audit_logs table

## Backup and Recovery

### Regular Backups
- Full database backup daily
- Transaction log backup every 15 minutes
- Point-in-time recovery available

### Data Retention
- Audit logs retained for 90 days
- User data retained per privacy policy
- Soft deletes used where appropriate

## Contact & Support

For database schema questions:
- Create GitHub issue with 'database' label
- Include table names and specific questions
- Reference this documentation in your issue

## Changelog

### Version 1.0.0 (2025-10-02)
- Initial schema design
- Core tables: users, data_records, api_keys, audit_logs
- Basic relationships and constraints
- Performance indexes

---

**Note**: This schema is designed for production use and may differ from development reference databases. Always develop against this documented structure.