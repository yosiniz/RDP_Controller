# rdpctl relay (buluşma/aktarma) sunucusu — bağımlılık YOK (saf stdlib).
# Derleme:  docker build -f packaging/relay.Dockerfile -t rdpctl-relay .
# Çalıştır: docker run -d --name rdpctl-relay -p 7444:7444 --restart unless-stopped rdpctl-relay
FROM python:3.12-slim

WORKDIR /app
# Relay yalnızca rdpctl/__init__.py, relay.py ve protocol.py'yi kullanır
# (hepsi stdlib). GUI/pip paketleri gerekmez.
COPY rdpctl/__init__.py ./rdpctl/__init__.py
COPY rdpctl/relay.py ./rdpctl/relay.py
COPY rdpctl/protocol.py ./rdpctl/protocol.py
COPY run_relay.py ./run_relay.py

EXPOSE 7444
ENTRYPOINT ["python", "-m", "rdpctl.relay", "--host", "0.0.0.0", "--port", "7444"]
