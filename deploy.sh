#!/usr/bin/env bash
# deploy.sh — build, push to AWS ECR, and force a new ECS Fargate deployment.
#
# Required environment variables:
#   AWS_ACCOUNT_ID   — your 12-digit AWS account ID
#   AWS_REGION       — e.g. us-east-1
#
# Optional:
#   IMAGE_TAG        — defaults to the short git SHA
#   ECS_CLUSTER      — defaults to "smart-suggest-cluster"
#   ECS_SERVICE      — defaults to "smart-suggest-service"

set -euo pipefail

APP_NAME="smart-suggest"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
AWS_REGION="${AWS_REGION:?'AWS_REGION is required'}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?'AWS_ACCOUNT_ID is required'}"
ECS_CLUSTER="${ECS_CLUSTER:-${APP_NAME}-cluster}"
ECS_SERVICE="${ECS_SERVICE:-${APP_NAME}-service}"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${APP_NAME}"

echo "━━━ smart-suggest deploy ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Image tag : ${IMAGE_TAG}"
echo "  ECR repo  : ${ECR_URI}"
echo "  Cluster   : ${ECS_CLUSTER} / ${ECS_SERVICE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Authenticate Docker with ECR
echo "→ Authenticating with ECR..."
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_URI}"

# 2. Ensure the ECR repository exists
aws ecr describe-repositories --repository-names "${APP_NAME}" \
    --region "${AWS_REGION}" > /dev/null 2>&1 \
  || aws ecr create-repository --repository-name "${APP_NAME}" \
      --region "${AWS_REGION}" --output text

# 3. Build production image
echo "→ Building production image..."
docker build --target production -t "${APP_NAME}:${IMAGE_TAG}" .
docker tag "${APP_NAME}:${IMAGE_TAG}" "${ECR_URI}:${IMAGE_TAG}"
docker tag "${APP_NAME}:${IMAGE_TAG}" "${ECR_URI}:latest"

# 4. Push to ECR
echo "→ Pushing to ECR..."
docker push "${ECR_URI}:${IMAGE_TAG}"
docker push "${ECR_URI}:latest"

# 5. Force new ECS deployment
echo "→ Triggering ECS deployment..."
aws ecs update-service \
  --cluster "${ECS_CLUSTER}" \
  --service "${ECS_SERVICE}" \
  --force-new-deployment \
  --region "${AWS_REGION}" \
  --output text > /dev/null

echo "✓ Deployed ${ECR_URI}:${IMAGE_TAG}"
echo "  Monitor: https://console.aws.amazon.com/ecs/home?region=${AWS_REGION}#/clusters/${ECS_CLUSTER}/services/${ECS_SERVICE}"
