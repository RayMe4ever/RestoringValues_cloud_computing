pipeline {
  agent { label 'ia_bakastov_lable' }

  options {
    timestamps()
    timeout(time: 25, unit: 'MINUTES')
    disableConcurrentBuilds()
  }

  parameters {
    string(name: 'BUILD_JOB', defaultValue: 'ia_bakastov_cloud_computing/ia_bakastov_pipline', description: 'L2 job that produces dist/*.whl and app-restoringvalues.tgz')
    string(name: 'SSH_CRED_ID', defaultValue: 'deploy_ssh_ia_bakastov', description: 'Jenkins credential: SSH username with private key to access VM')
    choice(name: 'TF_ACTION', choices: ['apply', 'destroy'], description: 'Terraform action')
  }

  environment {
    TF_IN_AUTOMATION = '1'
    TF_INPUT = '0'
  }

  stages {

    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Fetch artifacts from L2') {
      steps {
        script {
          sh 'rm -rf deploy_art && mkdir -p deploy_art'
          step([
            $class: 'CopyArtifact',
            projectName: params.BUILD_JOB,
            selector: [$class: 'StatusBuildSelector', stable: false],
            filter: 'dist/*.whl',
            target: 'deploy_art',
            fingerprintArtifacts: true
          ])
          step([
            $class: 'CopyArtifact',
            projectName: params.BUILD_JOB,
            selector: [$class: 'StatusBuildSelector', stable: false],
            filter: 'app-restoringvalues.tgz',
            target: 'deploy_art',
            fingerprintArtifacts: true
          ])
          sh 'find deploy_art -maxdepth 3 -type f -print'
        }
      }
    }

    stage('Terraform init') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail

          # 1) Подать OpenStack креды (без этого provider пустой)
          . /home/ubuntu/students-openrc.sh

          # 2) Быстрый smoke-check что токен реально получается
          openstack token issue >/dev/null

          terraform -version

          # 3) зеркала провайдеров
          if [ -f terraform.rc ]; then
            export TF_CLI_CONFIG_FILE="$PWD/terraform.rc"
            echo "Using existing terraform.rc from repo"
          fi

          terraform init -upgrade
        '''
      }
    }

    stage('Terraform apply') {
      when { expression { params.TF_ACTION == 'apply' } }
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail

          . /home/ubuntu/students-openrc.sh
          openstack token issue >/dev/null

          terraform apply -auto-approve

          terraform output -raw vm_ip | tee vm_ip.txt
          echo
          echo "VM_IP=$(cat vm_ip.txt)"
        '''
      }
    }

    stage('Ansible deploy') {
      when { expression { params.TF_ACTION == 'apply' } }
      steps {
        withCredentials([sshUserPrivateKey(
          credentialsId: params.SSH_CRED_ID,
          keyFileVariable: 'SSH_KEY_FILE',
          usernameVariable: 'SSH_USER'
        )]) {
          sh '''#!/usr/bin/env bash
            set -euo pipefail

            chmod 600 "$SSH_KEY_FILE"

            VM_IP="$(cat vm_ip.txt)"
            echo "VM_IP=$VM_IP"

            WHEEL="$(ls -1 deploy_art/**/*.whl deploy_art/*.whl 2>/dev/null | head -n 1 || true)"
            if [ -z "$WHEEL" ]; then
              echo "No .whl found. Listing deploy_art:"
              find deploy_art -maxdepth 4 -type f -print || true
              exit 1
            fi

            TGZ="$(ls -1 deploy_art/*.tgz 2>/dev/null | head -n 1 || true)"
            if [ -z "$TGZ" ]; then
              echo "No .tgz found. Listing deploy_art:"
              find deploy_art -maxdepth 2 -type f -print || true
              exit 1
            fi

            echo "Using wheel: $WHEEL"
            echo "Using tgz:   $TGZ"

            echo "==> Wait for SSH..."
            for i in $(seq 1 60); do
              if ssh -i "$SSH_KEY_FILE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ${SSH_USER}@${VM_IP} "echo ok" >/dev/null 2>&1; then
                break
              fi
              sleep 2
            done

            ansible-playbook -i "${VM_IP}," playbook.yml \
              --user "${SSH_USER}" --private-key "$SSH_KEY_FILE" \
              --ssh-common-args "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
              --extra-vars "wheel_path=${WHEEL} app_tgz_path=${TGZ} release_id=${BUILD_NUMBER}"
          '''
        }
      }
    }

    stage('Terraform destroy') {
      when { expression { params.TF_ACTION == 'destroy' } }
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail

          . /home/ubuntu/students-openrc.sh
          openstack token issue >/dev/null

          if [ -f terraform.rc ]; then
            export TF_CLI_CONFIG_FILE="$PWD/terraform.rc"
            echo "Using existing terraform.rc from repo"
          fi

          terraform init -upgrade
          terraform destroy -auto-approve
        '''
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'deploy_art/**, vm_ip.txt, terraform.tfstate*, .terraform.lock.hcl', allowEmptyArchive: true
      cleanWs()
    }
  }
}
