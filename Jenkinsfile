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
      description: 'Optional Docker image tag override (default: BUILD_NUMBER)'
    )
  }

  environment {
    IMAGE_NAME = 'abduuu0/prompt-firewall'
    SBOM_FILE = 'bom.json'
    GITLEAKS_REPORT = 'gitleaks-report.json'
    PIP_AUDIT_REPORT = 'pip-audit-report.json'
    TRIVY_REPORT = 'trivy-report.json'
    MLFLOW_TRACKING_URI = 'http://localhost:5000'

    // Optional: define this in Jenkins global env or credentials config
    // DOCKERHUB_CREDENTIALS_ID = 'dockerhub-creds'
  }

  stages {

    stage('Init') {
      steps {
        script {
          env.IMAGE_TAG = params.MODEL_IMAGE_TAG?.trim() ? params.MODEL_IMAGE_TAG.trim() : env.BUILD_NUMBER

          env.RUN_SETUP   = (params.PIPELINE_MODE in ['full', 'prepare-data-only', 'train-only']) ? 'true' : 'false'
          env.RUN_QUALITY = (params.PIPELINE_MODE == 'full') ? 'true' : 'false'
          env.RUN_PREPARE = (params.PIPELINE_MODE in ['full', 'prepare-data-only']) ? 'true' : 'false'
          env.RUN_TRAIN   = (params.PIPELINE_MODE in ['full', 'train-only']) ? 'true' : 'false'
          env.RUN_DEPLOY  = (params.PIPELINE_MODE in ['full', 'deploy-only']) ? 'true' : 'false'

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

    stage('Install') {
      when {
        expression { env.RUN_SETUP == 'true' }
      }
      steps {
        sh '''
          rm -rf .venv
          python3 -m venv .venv
          . .venv/bin/activate
          pip install --upgrade pip
          pip install -r requirements.txt
          pip install -e .
        '''
      }
    }

    stage('Lint & Test') {
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

    stage('Security Scans - Source') {
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

    stage('Train') {
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

    stage('Generate SBOM') {
      when {
        expression { env.RUN_DEPLOY == 'true' }
      }
      steps {
        script {
          // If deploy-only does not install Python deps, install tool temporarily only if needed
          sh '''
            if [ ! -d ".venv" ]; then
              python3 -m venv .venv
              . .venv/bin/activate
              pip install --upgrade pip
              pip install cyclonedx-bom
            else
              . .venv/bin/activate
              pip install cyclonedx-bom
            fi

            cyclonedx-py environment --of JSON --output-file ${SBOM_FILE}
          '''
        }
      }
      post {
        always {
          archiveArtifacts artifacts: "${SBOM_FILE}", onlyIfSuccessful: false
        }
      }
    }

    stage('Upload SBOM to Dependency-Track') {
      when {
        expression { env.RUN_DEPLOY == 'true' }
      }
      steps {
        script {
          if (!env.DEPENDENCY_TRACK_URL?.trim() ||
              !env.DEPENDENCY_TRACK_API_KEY?.trim() ||
              !env.DEPENDENCY_TRACK_PROJECT_UUID?.trim()) {
            error('Dependency-Track configuration missing: DEPENDENCY_TRACK_URL / DEPENDENCY_TRACK_API_KEY / DEPENDENCY_TRACK_PROJECT_UUID')
          }
        }

        sh '''
          curl -X POST "$DEPENDENCY_TRACK_URL/api/v1/bom" \
            -H "X-Api-Key: $DEPENDENCY_TRACK_API_KEY" \
            -F "project=$DEPENDENCY_TRACK_PROJECT_UUID" \
            -F "bom=@${SBOM_FILE}"
        '''
      }
    }

    stage('Build Docker Image') {
      when {
        expression { env.RUN_DEPLOY == 'true' }
      }
      steps {
        sh '''
          docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
          docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${IMAGE_NAME}:latest
        '''
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
        allOf {
          expression { env.RUN_DEPLOY == 'true' }
          expression { env.DOCKERHUB_CREDENTIALS_ID?.trim() }
        }
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
  }

  post {
    always {
      echo "Pipeline finished with mode: ${params.PIPELINE_MODE}"
    }
    success {
      echo 'Pipeline completed successfully.'
    }
    unstable {
      echo 'Pipeline completed with warnings (UNSTABLE).'
    }
    failure {
      echo 'Pipeline failed.'
    }
  }
}