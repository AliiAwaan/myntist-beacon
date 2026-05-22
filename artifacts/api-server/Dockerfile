FROM public.ecr.aws/docker/library/node:20-slim AS builder

WORKDIR /workspace

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY lib/ ./lib/
COPY artifacts/api-server/ ./artifacts/api-server/

RUN npm install -g pnpm && pnpm install --frozen-lockfile
RUN pnpm --filter @workspace/api-server run build

FROM public.ecr.aws/docker/library/node:20-slim AS runner

WORKDIR /app

RUN npm install -g pnpm

COPY --from=builder /workspace/package.json ./
COPY --from=builder /workspace/pnpm-workspace.yaml ./
COPY --from=builder /workspace/pnpm-lock.yaml ./
COPY --from=builder /workspace/lib/ ./lib/
COPY --from=builder /workspace/artifacts/api-server/dist/ ./artifacts/api-server/dist/
COPY --from=builder /workspace/artifacts/api-server/package.json ./artifacts/api-server/

RUN pnpm install --frozen-lockfile --prod

ENV NODE_ENV=production
ENV PORT=3001

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3001/health', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

CMD ["node", "--enable-source-maps", "./artifacts/api-server/dist/index.mjs"]
