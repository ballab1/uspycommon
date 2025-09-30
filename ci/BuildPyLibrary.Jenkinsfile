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
    DEVPI_SERVER = 'http://devpi.prod.k8s.home/'
    DEVPI_INDEX = 'testuser/dev'
//    DEVPI_REPO = 'devpi'
//    PYPIRC_FILE = 'ci/stg-pypirc'
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
          uploadPythonPackage([ venv: "$VENV",
                                credentialsid: 'DEV_PI_CREDS',
                                package_dir: "$PACKAGE_DIR",
                                usedevpi: true,
                                devpi_server: "$DEVPI_SERVER",
                                devpi_index: "$DEVPI_INDEX"])
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
