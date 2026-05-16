pipeline {
    agent any

    environment {
        ECR_REGISTRY = "public.ecr.aws/e8i6o3e4"
        ECR_REPO     = "odoo-deploy"
        IMAGE_TAG    = "${BUILD_NUMBER}"
        SONAR_TOKEN  = credentials('SONAR_TOKEN')

        // FIXED PROJECT PATH
        PROJECT_DIR  = "/home/ubuntu/odoo-tobarcata"

        // FIXED NETWORK NAME
        DOCKER_NET   = "odoo-tobarcata_odoo-net"
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

        stage('Deploy') {
            steps {
                sh """
                set -e

                echo "Pull latest image..."
                docker pull ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG}

                echo "Checking project directory..."
                ls -la ${PROJECT_DIR}

                echo "Starting PostgreSQL..."
                cd ${PROJECT_DIR}

                docker compose up -d db

                echo "Waiting for DB..."
                sleep 20

                echo "Ensuring Docker network exists..."
                docker network inspect ${DOCKER_NET} >/dev/null 2>&1 || \
                docker network create ${DOCKER_NET}

                echo "Removing old Odoo container..."
                docker stop odoo18_tobarcata_web || true
                docker rm odoo18_tobarcata_web || true

                echo "Starting new Odoo container..."

                docker run -d \
                  --name odoo18_tobarcata_web \
                  --network ${DOCKER_NET} \
                  --restart always \
                  -p 8070:8069 \
                  -e HOST=db \
                  -e USER=odoo \
                  -e PASSWORD=odoo \
                  -v odoo-tobarcata_odoo_data:/var/lib/odoo \
                  -v ${PROJECT_DIR}/addons:/mnt/extra-addons \
                  -v ${PROJECT_DIR}/enterprise-addons:/mnt/enterprise-addons \
                  ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG} \
                  odoo -c /etc/odoo/odoo.conf -d tobarcota_db

                echo "Deployment completed."
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
