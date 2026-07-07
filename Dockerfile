FROM python:3.12-alpine

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Hugging Face Spaces bind to port 7860 by default
ENV PORT=7860
EXPOSE 7860

# Run the bot
CMD ["python", "bot.py"]
