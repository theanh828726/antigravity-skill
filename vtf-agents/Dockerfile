FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY pyproject.toml ./
COPY src ./src
RUN pip install .
RUN useradd -m app && mkdir -p /app/data && chown -R app /app/data
USER app
CMD ["python", "-m", "vtf"]
