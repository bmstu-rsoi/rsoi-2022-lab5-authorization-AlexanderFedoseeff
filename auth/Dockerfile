FROM python:3.10.4
EXPOSE 8040
WORKDIR /app
COPY app.py /app/app.py
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt
CMD ["python3", "app.py"]