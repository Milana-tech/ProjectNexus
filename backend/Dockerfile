FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN useradd -m -u 10001 appuser

COPY --chown=appuser:appuser requirements.txt ./
RUN chown -R appuser:appuser /opt/venv

USER appuser

RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . ./

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
