@Library('jenkins-sharedlibs')_

pipeline {
  agent {
    kubernetes {
      cloud 'Kubernetes-dev'
      defaultContainer 'jnlp'
      yamlFile 'ci/buildPyLibrary.yaml'
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
    PYPIRC_FILE = 'ci/stg-pypirc'
    DEVPI_SERVER = 'http://devpi.prod.k8s.home/'
    DEVPI_INDEX = 'testuser/dev'
  }


  stages {
    stage('Configure Build Containers') {
      steps {
        container('python') {
          sh """
            source ${VENV}/bin/activate
            ${PYTHON} -m build
          """
        }
      }
    }

    stage('Archive Artifacts') {
      steps {
        container('python') {
          archiveArtifacts artifacts: "${PACKAGE_DIR}/*.whl,${PACKAGE_DIR}/*.tar.gz", fingerprint: true
        }
      }
    }

    stage('Upload to DevPi') {
      steps {
        container('python') {
          withCredentials([usernamePassword(credentialsId: 'DEV_PI_CREDS', passwordVariable: 'DEVPI_PASSWORD', usernameVariable: 'DEVPI_USER')]) {
            sh """
              source ${VENV}/bin/activate
              devpi use ${DEVPI_SERVER}/${DEVPI_INDEX}
              devpi login ${DEVPI_USER} --password=${DEVPI_PASSWORD}
              devpi upload --from-dir ${PACKAGE_DIR}
            """
          }
        }
      }
    }

    stage('Push Package') {
      when { expression { 0 == 1 } }
      steps {
        container('python') {
          withCredentials([usernamePassword(credentialsId: 'DEV_PI_CREDS', passwordVariable: 'TWINE_PASSWORD', usernameVariable: 'TWINE_USER')]) {
            sh """
              var='123'
              echo "TWINE_USER: $TWINE_USER, TWINE_PASSWORD: $var"
              source ${VENV}/bin/activate
              ${PYTHON} -m twine upload --verbose --disable-progress-bar --non-interactive  --repository devpi ./${PACKAGE_DIR}/* --config-file $PYPIRC_FILE
            """
          }
        }
      }
    }
  }

  post {
    always {
      kafkaBuildReporter()
    }
  }
}
