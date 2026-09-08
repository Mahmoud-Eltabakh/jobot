#!/usr/bin/env bash
set -euo pipefail

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment-ollama.yaml
kubectl apply -f k8s/deployment-jobot.yaml
kubectl apply -f k8s/ingress.yaml
kubectl rollout status deployment/jobot-deployment -n jobot --timeout=180s
