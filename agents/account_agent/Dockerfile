FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared ./shared
COPY agents/account_agent .


EXPOSE 8003

CMD ["python", "main.py"]
