@Library('jenkins-sharedlibs')_


pipeline {
    agent { label 's3.ubuntu.home' }

    environment {
        DOCKER_IMAGE = 'registry.ubuntu.home/alpine/python/3.13.2'
        DOCKER_TAG = "${env.BUILD_NUMBER}"
        DOCKER_REGISTRY = 'registry.ubuntu.home'  // e.g., index.docker.io or registry.example.com
        DOCKER_CREDENTIALS_ID = '1a69cdbb-be20-4bde-b30a-87ef9b2db969'
    }

    stages {
        stage('Build Image') {
            steps {
                script {
                    docker.build("${DOCKER_IMAGE}:${DOCKER_TAG}", 'ci')
                }
            }
        }

        stage('Push Image') {
            steps {
                script {
                    docker.withRegistry("https://${DOCKER_REGISTRY}", "${DOCKER_CREDENTIALS_ID}") {
                        docker.image("${DOCKER_IMAGE}:${DOCKER_TAG}").push()
                    }
                }
            }
        }
    }
    post {
        always {
            kafkaBuildReporter()
        }
        cleanup {
            deleteDir()
        }
    }
}
