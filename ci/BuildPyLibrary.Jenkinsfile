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
    UNIT_TESTS = 0
    PACKAGE_DIR = 'dist'
    DEVPI_SERVER = 'http://devpi.prod.k8s.home/'
    DEVPI_INDEX = 'testuser/dev'
//    DEVPI_REPO = 'devpi'
//    PYPIRC_FILE = 'ci/stg-pypirc'
  }


  stages {
    stage('Static code checks') {
        steps {
            container('python') {
                sh 'flake8 --config ci/.flake8 src/'
            }
        }
    }

    stage('Tests & Code Coverage') {
        when { environment name: 'UNIT_TESTS', value: '1' }
        steps {
            container(name: 'python') {
                sh "${PYTHON} -m pytest --verbose --junit-xml reports/unit_tests.xml"
                archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/unit_tests.xml'
            }
        }
    }

    stage('Build package') {
        steps {
            container('python') {
                sh "${PYTHON} -m build"
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
                uploadPythonPackage([ credentialsid: 'DEV_PI_CREDS',
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
