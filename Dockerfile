FROM node:22.18.0-bookworm-slim@sha256:752ea8a2f758c34002a0461bd9f1cee4f9a3c36d48494586f60ffce1fc708e0e AS node

FROM node AS treatment-plan-ui
WORKDIR /build
COPY Modules/Treatment-Plan/frontend/package.json Modules/Treatment-Plan/frontend/package-lock.json ./
RUN npm ci
COPY Modules/Treatment-Plan/frontend/ ./
RUN npm run build

FROM node AS severity-deps
WORKDIR /build
COPY Modules/Severity-1.1.0/package.json Modules/Severity-1.1.0/package-lock.json ./
RUN npm ci --omit=dev

FROM python:3.13.5-slim-bookworm@sha256:4c2cf9917bd1cbacc5e9b07320025bdb7cdf2df7b0ceaccb55e9dd7e30987419

ENV PATH=/opt/venv/bin:/usr/local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends nginx supervisor \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/venv
COPY --from=node /usr/local/ /usr/local/
COPY deploy/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

WORKDIR /opt/insight
COPY Modules/ Modules/
COPY deploy/ deploy/
COPY --from=treatment-plan-ui /build/dist/ Modules/Treatment-Plan/frontend/dist/
COPY --from=severity-deps /build/node_modules/ Modules/Severity-1.1.0/node_modules/
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/nginx-proxy.conf /etc/nginx/insight-proxy.conf
COPY deploy/supervisord.conf /etc/supervisor/supervisord.conf

RUN addgroup --gid 10001 insight \
    && adduser --uid 10001 --gid 10001 --disabled-password --gecos "" insight \
    && mkdir -p /var/lib/insight/authentication /var/lib/insight/dashboard \
      /var/lib/insight/add-new-patient /var/lib/insight/diagnosis \
      /var/lib/insight/severity /var/lib/insight/medical-history \
      /var/lib/insight/ddi-checker /var/lib/insight/bn-manager \
      /var/lib/insight/suicide-risk /var/lib/insight/treatment-plan \
      /tmp/nginx-client /tmp/nginx-proxy /tmp/nginx-fastcgi /tmp/nginx-uwsgi /tmp/nginx-scgi \
    && chown -R 10001:10001 /var/lib/insight /tmp/nginx-* \
    && chmod 0755 /opt/insight/deploy/entrypoint.sh

USER 10001:10001
EXPOSE 8080
STOPSIGNAL SIGTERM
ENTRYPOINT ["/opt/insight/deploy/entrypoint.sh"]
