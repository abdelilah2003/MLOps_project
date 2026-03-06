pipeline {
  agent any

  options {
    timestamps()
  }

  parameters {
    choice(
      name: 'PIPELINE_MODE',
      choices: ['full', 'prepare-data-only', 'train-only', 'deploy-only'],
      description: 'Choose which pipeline flow to execute'
    )

    string(
      name: 'MODEL_IMAGE_TAG',
      defaultValue: '',
      description: 'Optional Docker image tag override'
    )
  }

  environment {
    IMAGE_NAME = 'abduuu0/prompt-firewall'
    SBOM_FILE = 'bom.json'
    GITLEAKS_REPORT = 'gitleaks-report.json'
    PIP_AUDIT_REPORT = 'pip-audit-report.json'
    TRIVY_REPORT = 'trivy-report.json'


    DEPENDENCY_TRACK_URL = 'http://localhost:8081'
    DEPENDENCY_TRACK_PROJECT_UUID = '6ff10df0-18c5-4785-9363-01ef1fb180ef'

    MLFLOW_TRACKING_URI = 'http://localhost:5000'
  }




  stages {

    stage('Init') {
      steps {
        script {

          env.IMAGE_TAG = params.MODEL_IMAGE_TAG?.trim() ? params.MODEL_IMAGE_TAG.trim() : env.BUILD_NUMBER

          env.RUN_SETUP   = (params.PIPELINE_MODE in ['full','prepare-data-only','train-only']) ? 'true' : 'false'
          env.RUN_QUALITY = (params.PIPELINE_MODE in ['full','train-only']) ? 'true' : 'false'
          env.RUN_PREPARE = (params.PIPELINE_MODE in ['full','prepare-data-only']) ? 'true' : 'false'
          env.RUN_TRAIN   = (params.PIPELINE_MODE in ['full','train-only']) ? 'true' : 'false'
          env.RUN_DEPLOY  = (params.PIPELINE_MODE in ['full','deploy-only']) ? 'true' : 'false'

          echo """
PIPELINE_MODE = ${params.PIPELINE_MODE}
IMAGE_TAG     = ${env.IMAGE_TAG}
RUN_SETUP     = ${env.RUN_SETUP}
RUN_QUALITY   = ${env.RUN_QUALITY}
RUN_PREPARE   = ${env.RUN_PREPARE}
RUN_TRAIN     = ${env.RUN_TRAIN}
RUN_DEPLOY    = ${env.RUN_DEPLOY}
"""
        }
      }
    }

    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Install Environment') {
      when {
        expression { env.RUN_SETUP == 'true' }
      }

      steps {
        sh '''
        if [ ! -d ".venv" ]; then
          echo "Creating Python virtual environment..."
          python3 -m venv .venv
        fi

        . .venv/bin/activate

        pip install --upgrade pip
        pip install -r requirements.txt
        pip install -e .
        '''
      }
    }

    stage('Lint & Tests') {
      when {
        expression { env.RUN_QUALITY == 'true' }
      }

      steps {
        sh '''
        . .venv/bin/activate

        ruff check src tests scripts
        black --check src tests scripts
        pytest -q
        '''
      }
    }

    stage('Security Scan (Source)') {
      when {
        expression { env.RUN_QUALITY == 'true' }
      }

      steps {

        script {

          catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {

            sh '''
            . .venv/bin/activate
            pip-audit -f json -o ${PIP_AUDIT_REPORT}
            '''

          }

          catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {

            sh '''
            docker run --rm -v "$PWD:/repo" -w /repo \
            zricethezav/gitleaks:v8.21.2 detect \
            --source . \
            --report-format json \
            --report-path ${GITLEAKS_REPORT} \
            --redact
            '''

          }

        }

      }

      post {
        always {
          archiveArtifacts artifacts: "${PIP_AUDIT_REPORT},${GITLEAKS_REPORT}", onlyIfSuccessful: false
        }
      }

    }

    stage('Prepare Data') {
      when {
        expression { env.RUN_PREPARE == 'true' }
      }

      steps {
        sh '''
        . .venv/bin/activate
        dvc repro prepare_data
        '''
      }
    }

    stage('Start MLflow') {
      when {
        expression { env.RUN_TRAIN == 'true' }
      }

      steps {
        sh '''
        . .venv/bin/activate

        if ! curl -fs http://localhost:5000 > /dev/null; then
          echo "Starting MLflow server..."

          nohup mlflow server \
          --backend-store-uri sqlite:///mlflow.db \
          --default-artifact-root ./mlruns \
          --host 0.0.0.0 \
          --port 5000 > mlflow.log 2>&1 &
        else
          echo "MLflow already running"
        fi
        '''
      }
    }

    stage('Train Model') {
      when {
        expression { env.RUN_TRAIN == 'true' }
      }

      steps {
        sh '''
        . .venv/bin/activate
        dvc repro train
        '''
      }
    }

    stage('Build Docker Image') {
      when {
        expression { env.RUN_DEPLOY == 'true' }
      }

      steps {
        sh '''
        docker build --pull -t ${IMAGE_NAME}:${IMAGE_TAG} .
        docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${IMAGE_NAME}:latest
        '''
      }
    }

    stage('Generate SBOM') {
      when {
        expression { env.RUN_DEPLOY == 'true' }
      }

      steps {
        sh '''
        . .venv/bin/activate
        pip install cyclonedx-bom

        cyclonedx-py environment --of JSON --output-file ${SBOM_FILE}
        '''
      }

      post {
        always {
          archiveArtifacts artifacts: "${SBOM_FILE}", onlyIfSuccessful: false
        }
      }
    }

    stage('Dependency-Track Health Check') {
      when {
        expression { env.RUN_DEPLOY == 'true' }
      }

      steps {

        sh '''

        echo "Checking Dependency Track..."

        if ! curl -fs http://localhost:8081/api/version > /dev/null; then

          echo "Starting Dependency Track services..."

          docker start mlops_project-dtrack-postgres-1 || true
          docker start mlops_project-dependency-track-apiserver-1 || true
          docker start mlops_project-dependency-track-frontend-1 || true

        fi

        for i in {1..30}; do

          if curl -fs http://localhost:8081/api/version > /dev/null; then
            echo "Dependency Track ready"
            exit 0
          fi

          echo "Waiting for Dependency Track..."
          sleep 5

        done

        echo "Dependency Track failed to start"
        exit 1

        '''
      }
    }


    stage('Upload SBOM') {

      when {
        expression { env.RUN_DEPLOY == 'true' }
      }

      steps {

        withCredentials([
          string(credentialsId: 'dependency-track-api-key', variable: 'DEPENDENCY_TRACK_API_KEY'),
          string(credentialsId: 'dependency-track-project-uuid', variable: 'DEPENDENCY_TRACK_PROJECT_UUID')
        ]) {

          sh '''
          curl -X POST "http://localhost:8081/api/v1/bom" \
            -H "X-Api-Key: $DEPENDENCY_TRACK_API_KEY" \
            -F "project=$DEPENDENCY_TRACK_PROJECT_UUID" \
            -F "bom=@${SBOM_FILE}"
          '''
        }

      }

    }



    stage('Trivy Image Scan') {
      when {
        expression { env.RUN_DEPLOY == 'true' }
      }

      steps {

        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {

          sh '''
          docker run --rm \
          -v /var/run/docker.sock:/var/run/docker.sock \
          -v "$PWD:/project" \
          aquasec/trivy:0.56.2 image \
          --severity HIGH,CRITICAL \
          --format json \
          --output /project/${TRIVY_REPORT} \
          ${IMAGE_NAME}:${IMAGE_TAG}
          '''

        }

      }

      post {
        always {
          archiveArtifacts artifacts: "${TRIVY_REPORT}", onlyIfSuccessful: false
        }
      }

    }

    stage('Push Docker Image') {
      when {
        expression { env.RUN_DEPLOY == 'true' }
      }

      steps {

        withCredentials([
          usernamePassword(
            credentialsId: env.DOCKERHUB_CREDENTIALS_ID,
            usernameVariable: 'DOCKER_USER',
            passwordVariable: 'DOCKER_PASS'
          )
        ]) {

          sh '''
          echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
          docker push ${IMAGE_NAME}:${IMAGE_TAG}
          docker push ${IMAGE_NAME}:latest
          '''

        }

      }
    }

    stage('Deploy Container') {
      when {
        expression { env.RUN_DEPLOY == 'true' }
      }

      steps {

        sh '''
        echo "Deploying container..."

        docker rm -f prompt-firewall || true

        docker run -d \
        -p 8000:8000 \
        --name prompt-firewall \
        ${IMAGE_NAME}:${IMAGE_TAG}
        '''
      }
    }

  }

  post {

    always {
      echo "Pipeline finished in mode: ${params.PIPELINE_MODE}"
    }

    success {
      echo "Pipeline completed successfully"
    }

    unstable {
      echo "Pipeline finished with warnings"
    }

    failure {
      echo "Pipeline failed"
    }

  }

}