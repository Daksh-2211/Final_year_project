pipeline {
    agent any

    environment {
        ECR_REGISTRY = "public.ecr.aws/e8i6o3e4"
        ECR_REPO     = "odoo-deploy"
        IMAGE_TAG    = "${BUILD_NUMBER}"

        SONAR_HOST   = "http://sonarqube:9000"
        SONAR_TOKEN  = credentials('SONAR_TOKEN')
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        // OWASP stage skipped intentionally
        stage('OWASP Dependency Check') {
            steps {
                echo "OWASP Dependency Check Skipped"
            }
        }

        stage('SonarQube Analysis') {
            steps {
                script {
                    def scannerHome = tool 'SonarScanner'

                    withSonarQubeEnv('SonarQube') {
                        sh """
                        ${scannerHome}/bin/sonar-scanner \
                        -Dsonar.projectKey=odoo18 \
                        -Dsonar.projectName=odoo18 \
                        -Dsonar.sources=. \
                        -Dsonar.host.url=${SONAR_HOST} \
                        -Dsonar.token=${SONAR_TOKEN}
                        """
                    }
                }
            }
        }

        stage('SonarQube Quality Gate') {
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh """
                docker build \
                  -t ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG} .
                """
            }
        }

        stage('Trivy Image Scan') {
            steps {
                sh """
                trivy image \
                  --exit-code 1 \
                  --severity HIGH,CRITICAL \
                  --format table \
                  ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG}
                """
            }
        }

        stage('Push to ECR') {
            steps {
                sh """
                aws ecr-public get-login-password --region us-east-1 | \
                docker login --username AWS --password-stdin public.ecr.aws

                docker push ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG}

                docker tag \
                  ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG} \
                  ${ECR_REGISTRY}/${ECR_REPO}:latest

                docker push ${ECR_REGISTRY}/${ECR_REPO}:latest
                """
            }
        }

        stage('Deploy') {
            steps {
                sh """
                docker pull ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG}

                cd /home/ubuntu/odoo-tobarcota

                sed -i 's|image: .*|image: ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG}|' docker-compose.yml

                docker compose up -d --force-recreate odoo
                """
            }
        }
    }

    post {

        failure {
            echo "Pipeline failed 🚨"
        }

        success {
            echo "Deployment successful 🚀"
            echo "Image: ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG}"
        }
    }
}
