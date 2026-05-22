FROM python:3.14-slim

WORKDIR /app

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple/ \
    --trusted-host pypi.tuna.tsinghua.edu.cn poetry

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
    && poetry config certificates.tsinghua.cert false \
    && poetry install --no-interaction --no-ansi --no-root

COPY . .

CMD ["sh", "-c", "uvicorn src.app.main:app --host 0.0.0.0 --port 8000"]