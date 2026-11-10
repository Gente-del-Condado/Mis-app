FROM python:3.13-alpine

ENV PYTHONUNBUFFERED=1
WORKDIR /installer
COPY install_jacksignal.py .
COPY jacksignal/ ./jacksignal/
CMD ["python", "/installer/install_jacksignal.py"]
