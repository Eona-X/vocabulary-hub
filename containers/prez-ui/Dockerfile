# Prez UI — Nuxt SPA frontend for Prez.
#
# Vendored from RDFLib/prez-ui@main docker/Dockerfile. Endpoint is a build arg
# because Nuxt bakes the value into the static bundle; the browser must reach
# the Prez API directly, so use the host-visible URL, not the compose DNS name.
# Node 22 LTS: older corepack shipped with 21.7.1 cannot load pnpm 11
# (ERR_VM_DYNAMIC_IMPORT_CALLBACK_MISSING). 22 ships a corepack that handles it.
ARG NODE_VERSION=22

FROM node:${NODE_VERSION}-alpine AS build
ARG NUXT_PUBLIC_PREZ_API_ENDPOINT=http://localhost:8000
ARG NUXT_PUBLIC_PREZ_AUTO_DETECT_HTML=true
ARG NUXT_PUBLIC_PREZ_AUTO_DETECT_MARKDOWN=true

WORKDIR /app
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable
# Pin pnpm 9: pnpm 11 (default in newer corepack) blocks lifecycle scripts by
# default (ERR_PNPM_IGNORED_BUILDS), which leaves sharp unbuilt and breaks
# `pnpm generate`. pnpm 9 still runs build scripts without explicit approval.
RUN corepack prepare pnpm@9.15.4 --activate
RUN pnpm dlx create-prez-app@latest prez-ui

WORKDIR /app/prez-ui
RUN pnpm install
RUN npm --platform=linux --arch=x64 --libc=musl rebuild sharp

ENV NUXT_PUBLIC_PREZ_API_ENDPOINT=$NUXT_PUBLIC_PREZ_API_ENDPOINT
ENV NUXT_PUBLIC_PREZ_AUTO_DETECT_HTML=$NUXT_PUBLIC_PREZ_AUTO_DETECT_HTML
ENV NUXT_PUBLIC_PREZ_AUTO_DETECT_MARKDOWN=$NUXT_PUBLIC_PREZ_AUTO_DETECT_MARKDOWN

RUN pnpm generate

FROM nginx:stable-alpine
COPY --from=build /app/prez-ui/.output/public /usr/share/nginx/html
COPY default.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
