group "default" {
  targets = [
    "api-gateway",
    "ws-server",
    "scrape-orchestrator",
    "proxy-manager",
    "alert-engine",
    "alert-dispatcher",
    "spider-workers",
    "pipeline",
    "ml",
    "ai-chat",
    "frontend",
  ]
}

target "api-gateway" {
  context = "."
  dockerfile = "services/api-gateway/Dockerfile"
  tags = ["localhost:5001/api-gateway:dev"]
  cache-from = ["type=local,src=.buildx-cache"]
  cache-to = ["type=local,dest=.buildx-cache,mode=max"]
}

target "ws-server" {
  context = "."
  dockerfile = "services/ws-server/Dockerfile"
  tags = ["localhost:5001/ws-server:dev"]
  cache-from = ["type=local,src=.buildx-cache"]
  cache-to = ["type=local,dest=.buildx-cache,mode=max"]
}

target "scrape-orchestrator" {
  context = "."
  dockerfile = "services/scrape-orchestrator/Dockerfile"
  tags = ["localhost:5001/scrape-orchestrator:dev"]
  cache-from = ["type=local,src=.buildx-cache"]
  cache-to = ["type=local,dest=.buildx-cache,mode=max"]
}

target "proxy-manager" {
  context = "."
  dockerfile = "services/proxy-manager/Dockerfile"
  tags = ["localhost:5001/proxy-manager:dev"]
  cache-from = ["type=local,src=.buildx-cache"]
  cache-to = ["type=local,dest=.buildx-cache,mode=max"]
}

target "alert-engine" {
  context = "."
  dockerfile = "services/alert-engine/Dockerfile"
  tags = ["localhost:5001/alert-engine:dev"]
  cache-from = ["type=local,src=.buildx-cache"]
  cache-to = ["type=local,dest=.buildx-cache,mode=max"]
}

target "alert-dispatcher" {
  context = "."
  dockerfile = "services/alert-dispatcher/Dockerfile"
  tags = ["localhost:5001/alert-dispatcher:dev"]
  cache-from = ["type=local,src=.buildx-cache"]
  cache-to = ["type=local,dest=.buildx-cache,mode=max"]
}

target "spider-workers" {
  context = "."
  dockerfile = "services/spider-workers/Dockerfile"
  tags = ["localhost:5001/spider-workers:dev"]
  cache-from = ["type=local,src=.buildx-cache"]
  cache-to = ["type=local,dest=.buildx-cache,mode=max"]
}

target "pipeline" {
  context = "."
  dockerfile = "services/pipeline/Dockerfile"
  tags = ["localhost:5001/pipeline:dev"]
  cache-from = ["type=local,src=.buildx-cache"]
  cache-to = ["type=local,dest=.buildx-cache,mode=max"]
}

target "ml" {
  context = "."
  dockerfile = "services/ml/Dockerfile"
  tags = ["localhost:5001/ml:dev"]
  cache-from = ["type=local,src=.buildx-cache"]
  cache-to = ["type=local,dest=.buildx-cache,mode=max"]
}

target "ai-chat" {
  context = "."
  dockerfile = "services/ai-chat/Dockerfile"
  tags = ["localhost:5001/ai-chat:dev"]
  cache-from = ["type=local,src=.buildx-cache"]
  cache-to = ["type=local,dest=.buildx-cache,mode=max"]
}

target "frontend" {
  context = "."
  dockerfile = "frontend/Dockerfile"
  tags = ["localhost:5001/frontend:dev"]
  cache-from = ["type=local,src=.buildx-cache"]
  cache-to = ["type=local,dest=.buildx-cache,mode=max"]
}
