pipeline {
  agent { label 'ia_bakastov_lable' }

  environment {
    PYTHONNOUSERSITE = "1"
    NAMESPACE        = "ia-bakastov-nms"
    REGISTRY_ID      = "crp9gbl4bna1t355qco6"
    IMAGE            = "cr.yandex/${REGISTRY_ID}/restoringvalues:latest"
  }

  options {
    timestamps()
    timeout(time: 25, unit: 'MINUTES')
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Fetch artifacts from L2') {
      steps {
        sh 'rm -rf deploy_art && mkdir -p deploy_art'
        copyArtifacts(projectName: 'ia_bakastov_cloud_computing/ia_bakastov_pipline', selector: lastSuccessful())
        // если артефакты лежат в dist/ и корне — подстрой под твою L2
        sh '''#!/usr/bin/env bash
          set -e
          echo "Artifacts:"
          find . -maxdepth 3 -type f -name "*.tgz" -o -name "*.whl" | sed 's|^./||'
          mkdir -p deploy_art/dist
          cp -f app-restoringvalues.tgz deploy_art/ || true
          cp -f dist/*.whl deploy_art/dist/ || true
          ls -la deploy_art deploy_art/dist
        '''
      }
    }

    stage('Docker build') {
      steps {
        sh '''#!/usr/bin/env bash
          set -e
          docker build -t "$IMAGE" -f Docker/Dockerfile .
        '''
      }
    }

    stage('Docker login + push to YCR') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail

          YC=/home/ubuntu/yandex-cloud/bin/yc

          # если yc не найден — сразу понятная ошибка
          test -x "$YC" || (echo "yc not found at $YC" && exit 1)

          echo "==> Get IAM token"
          TOKEN="$($YC iam create-token)"

          echo "==> Docker login to YCR"
          echo "$TOKEN" | docker login --username iam --password-stdin cr.yandex

          echo "==> Push image"
          docker push cr.yandex/crp9gbl4bna1t355qco6/restoringvalues:latest
        '''
      }
    }

    stage('Deploy to Kubernetes') {
      steps {
        sh '''#!/usr/bin/env bash
          set -e
          kubectl get ns "$NAMESPACE" >/dev/null 2>&1 || kubectl create ns "$NAMESPACE"

          # подставляем registry_id в манифест (без helm)
          sed "s|cr.yandex/<REGISTRY_ID>/restoringvalues:latest|$IMAGE|g" k8s/deployment.yaml | kubectl apply -n "$NAMESPACE" -f -
          kubectl apply -n "$NAMESPACE" -f k8s/service-simulator.yaml
          kubectl apply -n "$NAMESPACE" -f k8s/service-reciever.yaml
          kubectl apply -n "$NAMESPACE" -f k8s/service-business.yaml

          kubectl rollout status deploy/restoringvalues -n "$NAMESPACE" --timeout=120s
          kubectl get pods -n "$NAMESPACE"
          kubectl get svc -n "$NAMESPACE"
        '''
      }
    }

    stage('Show logs') {
      steps {
        sh '''#!/usr/bin/env bash
          set -e
          POD=$(kubectl get pods -n "$NAMESPACE" -l app=restoringvalues -o jsonpath="{.items[0].metadata.name}")
          echo "POD=$POD"
          kubectl logs -n "$NAMESPACE" "$POD" --tail=200 || true
        '''
      }
    }
  }
}
