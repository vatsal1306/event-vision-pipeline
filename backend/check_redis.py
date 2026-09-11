import redis
r = redis.Redis(host='localhost', port=6379, db=1)
print(f"Keys in Redis db 1: {r.keys()}")
