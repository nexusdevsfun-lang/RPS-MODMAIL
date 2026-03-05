# Use a slim, secure Python base image (Python 3.12 is current stable)
FROM python:3.12-slim

# Set working directory inside container
WORKDIR /app

# Copy requirements first → better caching during builds
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your bot files
COPY . .

# Make sure the bot runs as non-root (security best practice)
RUN useradd -m botuser
USER botuser

# The actual command to start your bot
CMD ["python", "bot.py"]
