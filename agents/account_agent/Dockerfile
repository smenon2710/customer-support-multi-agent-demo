FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared ./shared
COPY agents/account_agent .


EXPOSE 8003

CMD ["python", "main.py"]
