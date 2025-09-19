@Library('jenkins-sharedlibs')_

pipeline {
  agent {
    kubernetes {
      cloud 'Kubernetes-dev'
      defaultContainer 'python'
      yamlFile 'build/containerBuildPod.yaml'
      showRawYaml(false)
    }
  }

  options {
    buildDiscarder(logRotator(numToKeepStr: '5', daysToKeepStr: '10'))
    timestamps()
    timeout(activity: true, time: 60, unit: 'MINUTES')
  }

  environment {
    PYTHON = 'python'
    VENV = '/usr/src/venv'
    PACKAGE_DIR = 'dist'
  }


  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Configure Build Containers') {
      steps {
         sh """
           source ${VENV}/bin/activate
           ${PYTHON} -m build
         """
      }
    }

    stage('Archive Artifacts') {
      steps {
        archiveArtifacts artifacts: "${PACKAGE_DIR}/*.whl,${PACKAGE_DIR}/*.tar.gz", fingerprint: true
      }
    }

    stage('Upload to DevPi') {
      when { expression { 0 == 1 } }
      environment {
        DEVPI_SERVER = 'http://devpi.local:3141'
        DEVPI_USER = credentials('devpi-username')      // Jenkins credentials ID
        DEVPI_PASSWORD = credentials('devpi-password')  // Jenkins credentials ID
        DEVPI_INDEX = 'user/dev'                        // Adjust as needed
      }
      steps {
        sh """
          . ${VENV}/bin/activate
          devpi use ${DEVPI_SERVER}/${DEVPI_INDEX}
          devpi login ${DEVPI_USER} --password=${DEVPI_PASSWORD}
          devpi upload --from-dir ${PACKAGE_DIR}
        """
      }
    }

    stage('Push Package') {
      steps {
        withCredentials([usernamePassword(credentialsId: '1a69cdbb-be20-4bde-b30a-87ef9b2db969', passwordVariable: 'TWINE_PASSWORD', usernameVariable: 'TWINE_USERNAME')]) {
          sh """
            source ${VENV}/bin/activate
            ${PYTHON} -m twine upload --verbose --disable-progress-bar --non-interactive  --repository devpi ./dist/* --config-file $PYPIRC_FILE
          """
        }
      }
    }
  }

//  post {
//    always {
//      kafkaBuildReporter()
//    }
//  }
}
