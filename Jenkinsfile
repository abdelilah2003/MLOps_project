pipeline {
  agent any

  options {
    timestamps()
  }

  parameters {
    choice(name: 'PIPELINE_MODE', choices: ['full', 'train-only', 'deploy-only'], description: 'Choose what to run')
    choice(name: 'DVC_TARGET', choices: ['all', 'prepare_data', 'train', 'monitor'], description: 'DVC stage to run when training is enabled')
    string(name: 'MODEL_IMAGE_TAG', defaultValue: '', description: 'Optional image tag override (default: BUILD_NUMBER)')
  }

  environment {
    IMAGE_NAME = "abduuu0/prompt-firewall"
    IMAGE_TAG = "${params.MODEL_IMAGE_TAG?.trim() ? params.MODEL_IMAGE_TAG : env.BUILD_NUMBER}"

    SBOM_FILE = "bom.json"

    GITLEAKS_REPORT = "gitleaks-report.json"
    PIP_AUDIT_REPORT = "pip-audit-report.json"
    TRIVY_REPORT = "trivy-report.json"
    MLFLOW_TRACKING_URI = "http://localhost:5000"
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
      }
    }


    stage('Install') {
      steps {
        sh '''
          rm -rf .venv
          python3 -m venv .venv
          . .venv/bin/activate
          pip install --upgrade pip
          pip install -r requirements.txt
        '''
      }
    }



    stage('Lint & Test') {
      steps {
        sh '''
        . .venv/bin/activate
        ruff check src tests scripts
        black --check src tests scripts
        pytest -q
        '''
      }
    }

    stage('Security Scans') {
      steps {

        script {

          catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
            sh '''
            . .venv/bin/activate
            pip-audit -f json -o pip-audit-report.json
            '''
          }

          catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
            sh '''
            docker run --rm -v "$PWD:/repo" -w /repo \
            zricethezav/gitleaks:v8.21.2 detect \
            --source . \
            --report-format json \
            --report-path gitleaks-report.json \
            --redact
            '''
          }

        }

        archiveArtifacts artifacts: 'pip-audit-report.json', onlyIfSuccessful: false
        archiveArtifacts artifacts: 'gitleaks-report.json', onlyIfSuccessful: false
      }
    }

    stage('Train with DVC') {
      when {
        expression { return params.PIPELINE_MODE in ['full', 'train-only'] }
      }
      steps {
        script {

          if (params.DVC_TARGET == 'all') {

            sh '''
            . .venv/bin/activate
            dvc repro
            '''

          } else {

            sh """
            . .venv/bin/activate
            dvc repro ${params.DVC_TARGET}
            """

          }

        }
      }
    }

    stage('Generate SBOM') {
      when {
        expression { return params.PIPELINE_MODE in ['full', 'deploy-only'] }
      }
      steps {

        sh '''
        . .venv/bin/activate
        cyclonedx-py environment --of JSON --output-file bom.json
        '''

        archiveArtifacts artifacts: 'bom.json', onlyIfSuccessful: false
      }
    }

    stage('Upload SBOM to Dependency-Track') {
      when {
        expression { return params.PIPELINE_MODE in ['full', 'deploy-only'] }
      }
      steps {

        script {
          if (!env.DEPENDENCY_TRACK_URL?.trim() ||
              !env.DEPENDENCY_TRACK_API_KEY?.trim() ||
              !env.DEPENDENCY_TRACK_PROJECT_UUID?.trim()) {

            error('Dependency-Track configuration missing')

          }
        }

        sh '''
        curl -X POST "$DEPENDENCY_TRACK_URL/api/v1/bom" \
          -H "X-Api-Key: $DEPENDENCY_TRACK_API_KEY" \
          -F "project=$DEPENDENCY_TRACK_PROJECT_UUID" \
          -F "bom=@bom.json"
        '''
      }
    }

    stage('Build Docker Image') {
      when {
        expression { return params.PIPELINE_MODE in ['full', 'deploy-only'] }
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
        expression { return params.PIPELINE_MODE in ['full', 'deploy-only'] }
      }
      steps {

        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {

          sh '''
          docker run --rm \
          -v /var/run/docker.sock:/var/run/docker.sock \
          -v $PWD:/project \
          aquasec/trivy:0.56.2 image \
          --severity HIGH,CRITICAL \
          --format json \
          --output trivy-report.json \
          ${IMAGE_NAME}:${IMAGE_TAG}
          '''

        }

        archiveArtifacts artifacts: 'trivy-report.json', onlyIfSuccessful: false
      }
    }

    stage('Push Docker Image') {
      when {
        allOf {
          expression { return params.PIPELINE_MODE in ['full', 'deploy-only'] }
          expression { return env.DOCKERHUB_CREDENTIALS_ID != null }
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
}