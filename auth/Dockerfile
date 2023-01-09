FROM python:3.10.4
EXPOSE 8080
WORKDIR /app
COPY server.py /app/server.py
COPY requirements.txt /app/requirements.txt
COPY templates/home.html /app/templates/home.html
COPY .env /app/.env
RUN pip install -r requirements.txt
CMD ["python3", "server.py"]