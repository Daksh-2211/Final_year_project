pipeline {
    agent any

    environment {
        ECR_REGISTRY = "public.ecr.aws/e8i6o3e4"
        ECR_REPO     = "odoo-deploy"
        IMAGE_TAG    = "${BUILD_NUMBER}"
        SONAR_TOKEN  = credentials('SONAR_TOKEN')

        // EC2 deployment target
        EC2_HOST     = "13.201.2.114"
        EC2_USER     = "ubuntu"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('OWASP Dependency Check') {
            steps {
                echo 'OWASP skipped — low RAM environment.'
            }
        }

        stage('SonarQube Analysis') {
            steps {
                script {
                    def scannerHome = tool 'SonarScanner'

                    withSonarQubeEnv('SonarQube') {
                        sh """
                        ${scannerHome}/bin/sonar-scanner \
                        -Dsonar.javascript.node.maxspace=4096 \
                        -Dsonar.exclusions=node_modules/**
                        """
                    }
                }
            }
        }

        stage('SonarQube Quality Gate') {
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: false
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
                  --exit-code 0 \
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

        stage('Deploy on EC2 via SSH') {
            steps {
                sh """
                ssh -o StrictHostKeyChecking=no ${EC2_USER}@${EC2_HOST} << 'EOF'
                set -e

                echo "🚀 Moving to project directory..."
                cd /home/ubuntu/odoo-tobarcata

                echo "🔄 Updating docker-compose image..."
                sed -i 's|odoo-deploy:.*|odoo-deploy:${IMAGE_TAG}|' docker-compose.yml

                echo "📥 Pulling latest image..."
                docker compose pull

                echo "♻️ Restarting containers..."
                docker compose up -d --force-recreate

                echo "✅ Deployment successful!"
                EOF
                """
            }
        }
    }

    post {
        success {
            echo "Successfully deployed: ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG}"
        }

        failure {
            echo "Pipeline failed. Check logs carefully."
        }
    }
}
