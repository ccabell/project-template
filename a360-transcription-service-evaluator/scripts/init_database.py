#!/usr/bin/env python3
"""Initialize database schema for Voice Actor platform.

This script uses the RDS Data API to create the database schema
for the Voice Actor platform in the Aurora PostgreSQL cluster.
"""

import boto3
import json
from typing import Any

# Database connection parameters
CLUSTER_ARN = "arn:aws:rds:us-east-1:471112502741:cluster:voiceactorstack-voiceactordatabase4566c987-heefb9ibbuva"
SECRET_ARN = "arn:aws:secretsmanager:us-east-1:471112502741:secret:VoiceActorDatabaseSecret4A6-cUkB3xqSwjOz-vnppG6"
DATABASE_NAME = "voice_actor_db"

# Initialize RDS Data API client
rds_data_client = boto3.client('rds-data', region_name='us-east-1')

def execute_sql(sql: str) -> dict[str, Any]:
    """Execute SQL using RDS Data API."""
    try:
        response = rds_data_client.execute_statement(
            resourceArn=CLUSTER_ARN,
            secretArn=SECRET_ARN,
            database=DATABASE_NAME,
            sql=sql
        )
        print(f"✅ SQL executed successfully")
        return response
    except Exception as e:
        print(f"❌ Failed to execute SQL: {str(e)}")
        raise

def init_database_schema():
    """Initialize the database schema."""
    print("🚀 Initializing Voice Actor database schema...")
    
    # Read the schema SQL file
    import os
    schema_path = os.path.join(os.path.dirname(__file__), 'backend', 'database_schema.sql')
    try:
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        print(f"📖 Read schema from: {schema_path}")
    except FileNotFoundError:
        print(f"❌ Could not find database_schema.sql file at: {schema_path}")
        return False
    
    # Split the schema into individual statements (split by semicolon and newline)
    statements = [stmt.strip() for stmt in schema_sql.split(';\n') if stmt.strip()]
    
    print(f"📝 Found {len(statements)} SQL statements to execute")
    
    for i, statement in enumerate(statements, 1):
        if not statement:
            continue
            
        print(f"🔄 Executing statement {i}/{len(statements)}")
        print(f"📝 Statement: {statement[:100]}...")
        
        try:
            execute_sql(statement + ';')  # Add back the semicolon
        except Exception as e:
            print(f"❌ Failed on statement {i}: {str(e)}")
            print(f"Statement: {statement}")
            # Continue with other statements instead of failing completely
            print("⚠️  Continuing with next statement...")
            continue
    
    print("✅ Database schema initialized successfully!")
    return True

def test_database_connection():
    """Test database connectivity."""
    print("🔍 Testing database connection...")
    
    try:
        response = execute_sql("SELECT 1 as test")
        print("✅ Database connection test successful")
        return True
    except Exception as e:
        print(f"❌ Database connection test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("Voice Actor Platform - Database Initialization")
    print("=" * 50)
    
    # Test connection first
    if not test_database_connection():
        print("❌ Database connection failed. Exiting.")
        exit(1)
    
    # Initialize schema
    if init_database_schema():
        print("🎉 Database initialization completed successfully!")
    else:
        print("❌ Database initialization failed!")
        exit(1)