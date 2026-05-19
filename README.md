```shell
celery --app app.tasks.celery_app.celery worker --loglevel=info --pool gevent
```

```shell
celery --app notify_service.app.tasks.celery_app.celery flower
```

```shell
poetry export -f requirements.txt -o requirements.txt --without-hashes
```