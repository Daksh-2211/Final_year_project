pipeline {
    agent any
    environment {
        ECR_REGISTRY = "public.ecr.aws/e8i6o3e4"
        ECR_REPO     = "odoo-deploy"
        IMAGE_TAG    = "${BUILD_NUMBER}"
        SONAR_TOKEN  = credentials('SONAR_TOKEN')
    }
    stages {
        stage('Checkout') {
            steps { checkout scm }
        }
        stage('OWASP Dependency Check') {
            steps {
                echo 'OWASP skipped — low RAM environment. Run manually on dev machine.'
            }
        }
        stage('SonarQube Analysis') {
            steps {
                script {
                    def scannerHome = tool 'SonarScanner'
                    withSonarQubeEnv('SonarQube') {
                        sh "${scannerHome}/bin/sonar-scanner"
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
                sh "docker build -t ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG} ."
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
                docker tag ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG} \
                           ${ECR_REGISTRY}/${ECR_REPO}:latest
                docker push ${ECR_REGISTRY}/${ECR_REPO}:latest
                """
            }
        }
        stage('Deploy') {
            steps {
                sh """
                docker pull ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG}

                # Ensure DB and network are up
                cd /home/ubuntu/odoo-tobarcota && docker compose up -d db
                sleep 10

                docker stop odoo18_tobarcota_web || true
                docker rm odoo18_tobarcota_web || true

                docker run -d \
                  --name odoo18_tobarcota_web \
                  --network odoo-tobarcota_odoo-net \
                  --restart always \
                  -p 8070:8069 \
                  -e HOST=db \
                  -e USER=odoo \
                  -e PASSWORD=odoo \
                  -v odoo-tobarcota_odoo_data:/var/lib/odoo \
                  -v /home/ubuntu/odoo-tobarcota/addons:/mnt/extra-addons \
                  -v /home/ubuntu/odoo-tobarcota/enterprise-addons:/mnt/enterprise-addons \
                  ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG} \
                  odoo -c /etc/odoo/odoo.conf -d tobarcota_db
                """
            }
        }
    }
    post {
        failure { echo "Pipeline failed — check logs" }
        success { echo "Deployed: ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG}" }
    }
}
