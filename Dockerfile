FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 KEYGUARDIAN_DEPLOYMENT=local
WORKDIR /app
COPY requirements-server.txt ./
RUN pip install --no-cache-dir -r requirements-server.txt && useradd --uid 10001 --create-home guardian
COPY --chown=guardian:guardian app.py gunicorn.conf.py ./
COPY --chown=guardian:guardian engine ./engine
COPY --chown=guardian:guardian server ./server
COPY --chown=guardian:guardian config ./config
COPY --chown=guardian:guardian web ./web
RUN chown guardian:guardian /tmp && chmod 1777 /tmp
VOLUME ["/tmp"]
USER guardian
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3).read()"
CMD ["gunicorn", "--config", "gunicorn.conf.py", "server.wsgi:create_app()"]
