FROM mcr.microsoft.com/playwright/python:v1.39.0-jammy

WORKDIR /app

# تثبيت المتطلبات الأساسية، Xvfb، وأدوات الشبكة
RUN apt-get update && apt-get install -y \
    xvfb \
    wireguard-tools \
    resolvconf \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# تحميل أداة wgcf لتحويل Cloudflare WARP إلى WireGuard
RUN wget -O /usr/local/bin/wgcf https://github.com/ViRb3/wgcf/releases/download/v2.2.18/wgcf_2.2.18_linux_amd64 && \
    chmod +x /usr/local/bin/wgcf

# إنشاء سكربت لتشغيل WARP وتوجيهه لأوروبا (سويسرا/ألمانيا)
RUN echo '#!/bin/bash\n\
wgcf register --accept-tos\n\
wgcf generate\n\
sed -i "s/Endpoint = .*/Endpoint = 162.159.192.1:2408/" wgcf-profile.conf\n\
mkdir -p /etc/wireguard\n\
cp wgcf-profile.conf /etc/wireguard/warp.conf\n\
wg-quick up warp\n\
exec "$@"' > /start.sh && chmod +x /start.sh

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["/start.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
