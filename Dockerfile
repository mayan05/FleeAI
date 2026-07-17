FROM python:3.11-slim

WORKDIR /app

# Copy requirements file
COPY requirements.txt ./

# Install dependencies using standard pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY src/ ./src/

EXPOSE 8501

# Run the Streamlit app on all network interfaces
CMD ["python", "-m", "streamlit", "run", "src/app.py", "--server.address=0.0.0.0"]
