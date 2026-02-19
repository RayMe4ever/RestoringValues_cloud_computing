pipeline {
  agent { label 'ia_bakastov_lable' }

  parameters {
    choice(name: 'ACTION', choices: ['create_or_update', 'delete'], description: 'Действие со стеком')
    string(name: 'STACK_NAME', defaultValue: 'ia_bakastov_heat', description: 'Имя Heat stack')
    string(name: 'SERVER_NAME', defaultValue: 'ia_bakastov_vm', description: 'Имя VM внутри stack')
    string(name: 'NET_ID', defaultValue: '17eae9b6-2168-4a07-a0d3-66d5ad2a9f0e', description: 'UUID сети')
    string(name: 'KEY_NAME', defaultValue: 'ia_bakastov_deploy', description: 'Имя keypair в OpenStack')
    string(name: 'SECURITY_GROUP', defaultValue: 'students-general', description: 'Security group')
  }

  stages {

    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Check tools') {
      steps {
        sh '''
          set -e
          which openstack
          openstack --version
          python3 --version
        '''
      }
    }

    stage('Create/Update stack') {
      when { expression { params.ACTION == 'create_or_update' } }
      steps {
        withEnv([
          "STACK_NAME=${params.STACK_NAME}",
          "SERVER_NAME=${params.SERVER_NAME}",
          "NET_ID=${params.NET_ID}",
          "KEY_NAME=${params.KEY_NAME}",
          "SECURITY_GROUP=${params.SECURITY_GROUP}"
        ]) {
          sh '''
            set -eu

            . /home/ubuntu/students-openrc.sh
            openstack token issue >/dev/null

            echo "==> Params"
            echo "STACK_NAME=$STACK_NAME"
            echo "SERVER_NAME=$SERVER_NAME"
            echo "NET_ID=$NET_ID"
            echo "KEY_NAME=$KEY_NAME"
            echo "SECURITY_GROUP=$SECURITY_GROUP"

            echo "==> Try UPDATE first"
            if openstack stack update -t heat/stack.yaml -e heat/env.yaml \
              --parameter server_name="$SERVER_NAME" \
              --parameter net_id="$NET_ID" \
              --parameter key_name="$KEY_NAME" \
              --parameter security_group="$SECURITY_GROUP" \
              "$STACK_NAME" >/dev/null 2>&1; then
              echo "Update requested"
            else
              echo "Update failed -> try CREATE"
              openstack stack create -t heat/stack.yaml -e heat/env.yaml \
                --parameter server_name="$SERVER_NAME" \
                --parameter net_id="$NET_ID" \
                --parameter key_name="$KEY_NAME" \
                --parameter security_group="$SECURITY_GROUP" \
                "$STACK_NAME"
            fi

            echo "==> Waiting for stack..."
            i=1
            while [ "$i" -le 90 ]; do
              echo "---- poll #$i ----"

              # Пишем JSON в файл (без here-string)
              if openstack stack show "$STACK_NAME" -f json > stack.json 2> stack.err; then
                status=$(python3 -c "import json; print(json.load(open('stack.json')).get('stack_status',''))" || true)
                echo "Status: $status"

                case "$status" in
                  *_IN_PROGRESS)
                    sleep 10
                    ;;
                  *_COMPLETE)
                    echo "==> COMPLETE"
                    break
                    ;;
                  *_FAILED)
                    echo "==> FAILED"
                    openstack stack show "$STACK_NAME" || true
                    echo "==> Recent events:"
                    openstack stack event list "$STACK_NAME" | tail -n 50 || true
                    echo "==> Failures:"
                    openstack stack failures list "$STACK_NAME" || true
                    exit 1
                    ;;
                  *)
                    echo "Unexpected status: $status"
                    openstack stack show "$STACK_NAME" || true
                    openstack stack event list "$STACK_NAME" | tail -n 20 || true
                    sleep 5
                    ;;
                esac
              else
                echo "STACK SHOW ERROR:"
                cat stack.err || true
                echo "Recent events:"
                openstack stack event list "$STACK_NAME" | tail -n 15 || true
                sleep 5
              fi

              i=$((i+1))
            done

            echo "==> Final stack show"
            openstack stack show "$STACK_NAME" || true

            echo "==> Outputs"
            openstack stack output list "$STACK_NAME" || true
          '''
        }
      }
    }

    stage('Delete stack') {
      when { expression { params.ACTION == 'delete' } }
      steps {
        withEnv(["STACK_NAME=${params.STACK_NAME}"]) {
          sh '''
            set -eu

            . /home/ubuntu/students-openrc.sh
            openstack token issue >/dev/null

            echo "Deleting stack: $STACK_NAME"
            openstack stack delete -y "$STACK_NAME" || true

            echo "==> Waiting for delete..."
            i=1
            while [ "$i" -le 90 ]; do
              if openstack stack show "$STACK_NAME" >/dev/null 2>&1; then
                echo "Still exists (poll #$i), sleep 5s"
                sleep 5
              else
                echo "Deleted: $STACK_NAME"
                exit 0
              fi
              i=$((i+1))
            done

            echo "Delete timeout"
            exit 1
          '''
        }
      }
    }
  }

  post {
    success { echo "Pipeline SUCCESS" }
    failure { echo "Pipeline FAILED" }
  }
}
