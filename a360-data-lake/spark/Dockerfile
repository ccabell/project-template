FROM --platform=linux/amd64 public.ecr.aws/amazonlinux/amazonlinux:2023-minimal AS base

# Install required packages
RUN dnf install -y gcc python3 python3-devel

# Set up virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy the current directory contents
COPY . .

# Install dependencies
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install venv-pack==0.2.0 && \
    python3 -m pip install . && \
    python3 -m pip install great-expectations==0.18.7

# Verify great-expectations installation
RUN pip list | grep great-expectations

# Create package with proper permissions
RUN mkdir /venv-package && \
    venv-pack -f -o /venv-package/pyspark-env.tar.gz && \
    chmod ugo+r /venv-package/pyspark-env.tar.gz

# Use minimal base image instead of scratch for final stage
FROM public.ecr.aws/amazonlinux/amazonlinux:2023-minimal
COPY --from=base /venv-package/pyspark-env.tar.gz /venv-package/pyspark-env.tar.gz