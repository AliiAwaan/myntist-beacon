FROM public.ecr.aws/docker/library/node:20-slim AS builder

WORKDIR /workspace

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY tsconfig.base.json tsconfig.json ./
COPY lib/ ./lib/
COPY artifacts/beacon-dashboard/ ./artifacts/beacon-dashboard/

RUN npm install -g pnpm && pnpm install --frozen-lockfile

ENV BASE_PATH=/
ENV PORT=3000
ENV NODE_ENV=production

RUN pnpm --filter @workspace/beacon-dashboard run build

FROM public.ecr.aws/docker/library/nginx:1.25-alpine

COPY --from=builder /workspace/artifacts/beacon-dashboard/dist/public /usr/share/nginx/html

COPY artifacts/beacon-dashboard/nginx.conf /etc/nginx/conf.d/default.conf

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
