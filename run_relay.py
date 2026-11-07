#!/usr/bin/env python3
"""rdpctl relay (buluşma/aktarma) sunucusu giriş noktası.

Geliştirici bunu BİR KEZ, genel erişilebilir bir sunucuda çalıştırır:
    python3 run_relay.py --port 7444
Son kullanıcılar relay'e dokunmaz; uygulama otomatik bağlanır.
"""
from rdpctl.relay import main

if __name__ == "__main__":
    raise SystemExit(main())
