FROM python:3.13-slim

# Install system-level GraphViz (required for diagrams + pygraphviz)
RUN apt-get update && \
    apt-get install -y graphviz graphviz-dev gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application code
COPY app/ /app
WORKDIR /app

# Create output directory
RUN mkdir -p /app/diagrams

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
