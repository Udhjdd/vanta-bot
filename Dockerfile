FROM mcr.microsoft.com/playwright/python:v1.39.0-jammy

WORKDIR /app

# تثبيت الشاشة الوهمية Xvfb
RUN apt-get update && apt-get install -y xvfb && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
