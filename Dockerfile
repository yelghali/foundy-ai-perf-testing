FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir .

USER 65532
ENTRYPOINT ["ai-perf"]
CMD ["run-suite", "--profile", "smoke", "--warmups", "1", "--repetitions", "2"]
CMD ["run-suite", "--profile", "smoke", "--warmups", "1", "--repetitions", "2"]
