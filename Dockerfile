FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
COPY src/ src/
COPY data/ data/

RUN uv pip install --system --no-cache -e .

EXPOSE 8000

CMD ["uvicorn", "rootcause.main:app", "--host", "0.0.0.0", "--port", "8000"]
