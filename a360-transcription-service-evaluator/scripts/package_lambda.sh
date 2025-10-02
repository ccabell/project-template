#!/bin/bash
# Package Lambda function with dependencies for ZIP deployment

set -e

LAMBDA_DIR="backend/lambda_functions/api_handler"
BUILD_DIR="lambda_build"
ZIP_FILE="api_handler.zip"

echo "🚀 Packaging Lambda function..."

# Clean previous build
rm -rf "$BUILD_DIR"
rm -f "$ZIP_FILE"

# Create build directory
mkdir -p "$BUILD_DIR"

# Copy source code
cp "$LAMBDA_DIR/index.py" "$BUILD_DIR/"
cp "$LAMBDA_DIR/requirements.txt" "$BUILD_DIR/"

# Install dependencies to build directory
echo "📦 Installing dependencies..."
cd "$BUILD_DIR"

# Use Python from the CDK virtual environment if available, otherwise system python
if [ -f "../cdk/.venv/bin/pip" ]; then
    echo "Using CDK virtual environment pip..."
    ../cdk/.venv/bin/pip install -r requirements.txt --target . --platform linux_x86_64 --only-binary=:all:
else
    echo "Using system pip..."
    python3 -m pip install -r requirements.txt --target . --platform linux_x86_64 --only-binary=:all:
fi

# Remove unnecessary files to reduce size
rm -rf *.dist-info
rm -rf __pycache__
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -delete

# Create ZIP package
echo "🗜️  Creating ZIP package..."
zip -r "../$ZIP_FILE" . -x "requirements.txt"

cd ..
echo "✅ Lambda package created: $ZIP_FILE"
echo "📊 Package size: $(du -h $ZIP_FILE | cut -f1)"