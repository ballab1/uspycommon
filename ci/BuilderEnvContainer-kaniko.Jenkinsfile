@Library('jenkins-sharedlibs')_

pipeline {
    agent {
        kubernetes {
            cloud 'Kubernetes-dev'
            defaultContainer 'jnlp'
            yamlFile 'ci/containerBuildPod.yaml'
            showRawYaml(false)
        }
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '5', daysToKeepStr: '10'))
        timestamps()
        timeout(activity: true, time: 60, unit: 'MINUTES')
    }

    stages {
        stage('Configure Build Containers') {
            when { expression { currentBuild.currentResult == 'SUCCESS' } }
            steps {
              container('python') {
                 sh """
                    pwd
                    env
		    source /usr/src/venv/bin/activate
		    python -m build
                 """
              }
            }
        }

        stage('Push Package') {
            when {
                allOf {
                    expression { currentBuild.currentResult == 'SUCCESS' }
                    anyOf {
                        branch 'main'
                    }
                }
            }
            steps {
              container('python') {
                withCredentials([usernamePassword(credentialsId: '1a69cdbb-be20-4bde-b30a-87ef9b2db969', passwordVariable: 'TWINE_PASSWORD', usernameVariable: 'TWINE_USERNAME')]) {
                  sh """
		    source /usr/src/venv/bin/activate
	            python -m twine upload --verbose --disable-progress-bar --non-interactive  --repository devpi ./dist/* --config-file $PYPIRC_FILE
                  """
                }
              }
            }
        }
    }

//    post {
//        always {
//            kafkaBuildReporter()
//        }
//    }
}
