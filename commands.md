```bash
docker run -d \
  --name easy_convert-redis \
  -p 6379:6379 \
  redis

```

```bash
# install redis cli if not exists
sudo apt-get install redis
# test connection
redis-cli ping
# should return "PONG"
```