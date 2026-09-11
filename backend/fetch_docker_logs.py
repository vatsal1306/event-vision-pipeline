import docker
client = docker.from_env()
container = client.containers.get('backend-celery-worker-1')
logs = container.logs(tail=100).decode('utf-8')
print(logs)
