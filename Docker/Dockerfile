FROM python:3.10-slim

RUN apt-get update && apt-get install -y tar && rm -rf /var/lib/apt/lists/*

# структура как на VM
RUN mkdir -p /opt/restoringvalues/releases /opt/restoringvalues/current /opt/restoringvalues/run
RUN mkdir -p /opt/restoringvalues/run
WORKDIR /opt/restoringvalues

COPY deploy_art/app-restoringvalues.tgz /tmp/app-restoringvalues.tgz
COPY deploy_art/dist/restoringvalues-0.1.0-py3-none-any.whl /tmp/restoringvalues-0.1.0-py3-none-any.whl

# ВАЖНО: распаковываем В app/
RUN mkdir -p /opt/restoringvalues/current/app \
 && tar -xzf /tmp/app-restoringvalues.tgz -C /opt/restoringvalues/current/app

# wheel ставим по реальному имени файла
RUN pip install --no-cache-dir /tmp/restoringvalues-0.1.0-py3-none-any.whl

COPY Docker/start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
