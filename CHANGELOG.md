# DRP Microservice Framework Changelog


## v2.4.1
- Support DLQ topic with secure Kafka [DDT-3219](https://jira.cec.lab.emc.com/browse/DDT-3219)

## v2.4.0
- Add DLQ Support for Kafka Consumer [DDRP-10803](https://jira.cec.lab.emc.com/browse/DDRP-10803).
- Upgrade cryptography version to 42.0.5 [DDRP-10803](https://jira.cec.lab.emc.com/browse/DDRP-10803).

## v2.3.1

- Upgrade certifi version to 2024.2.2 [DDRP-7850](https://jira.cec.lab.emc.com/browse/DDRP-7850).
- Upgrade idna version to 3.6 [DDRP-7850](https://jira.cec.lab.emc.com/browse/DDRP-7850).
- Upgrade kubernetes version to 29.0.0 [DDRP-7850](https://jira.cec.lab.emc.com/browse/DDRP-7850).
- Upgrade prometheus-client version to 0.19.0 [DDRP-7850](https://jira.cec.lab.emc.com/browse/DDRP-7850).
- Upgrade python-json-logger version to 2.0.7 [DDRP-7850](https://jira.cec.lab.emc.com/browse/DDRP-7850).
- Upgrade PyJWT version to 2.8.0 [DDRP-7850](https://jira.cec.lab.emc.com/browse/DDRP-7850).
- Upgrade requests version to 2.31.0 [DDRP-7850](https://jira.cec.lab.emc.com/browse/DDRP-7850).
- Upgrade wrapt version to 1.16.0 [DDRP-7850](https://jira.cec.lab.emc.com/browse/DDRP-7850).
- Upgrade cryptography version to 42.0.0 [DDRP-7850](https://jira.cec.lab.emc.com/browse/DDRP-7850).
- Upgrade build version to 1.0.3 [DDRP-7850](https://jira.cec.lab.emc.com/browse/DDRP-7850).
- Reformat source codes due to flake8 [DDRP-7850](https://jira.cec.lab.emc.com/browse/DDRP-7850).
- Update USPY build to new pipeline [DDRP-7850](https://jira.cec.lab.emc.com/browse/DDRP-7850).
- flush function is available for Kafka producer and signal handler will close producers [DDRP-11581](https://jira.cec.lab.emc.com/browse/DDRP-11581).

## v2.3.0

- Kafka consumer can get current partition assignment [DDRP-11272](https://jira.cec.lab.emc.com/browse/DDRP-11272).
- Kafka consumer can return min and max offsets for a topic partition [DDRP-11274](https://jira.cec.lab.emc.com/browse/DDRP-11274).
- Add StatusReporter for supporting the new Intermediate workflow [DDRP-10163](https://jira.cec.lab.emc.com/browse/DDRP-10163).
- Fix job manager cache issue when restartPolicy is Never and backoffLimit is set [DDT-2885](https://jira.cec.lab.emc.com/browse/DDT-2885).
- Reduce CPU consumption in KafkaConsumer when it is paused [DDT-2984](https://jira.cec.lab.emc.com/browse/DDT-2984).

## v2.2.4

- Add pod label for jobs [DDRP-10981](https://jira.cec.lab.emc.com/browse/DDRP-10981)
- Add job call back handle [DDRP-9979](https://jira.cec.lab.emc.com/browse/DDRP-9979)

## v2.2.3

- Kafka authentication support for helper.py [DDRP-8868](https://jira.cec.lab.emc.com/browse/DDRP-8868).
- Kafka consumer can set position for partition to offset [DDRP-10231](https://jira.cec.lab.emc.com/browse/DDRP-10231).
- Fix wrong offset validation and assignment when consumer starts [DDT-2271](https://jira.cec.lab.emc.com/browse/DDT-2271).
- Change message log order for faster log read [DDT-2305](https://jira.cec.lab.emc.com/browse/DDT-2305).

## v2.2.2

- Upgrade PyYAML version to v6.0.1 [DDRP-10312](https://jira.cec.lab.emc.com/browse/DDRP-10312).
- Deprecate get_secret, wait, wait_for methods in framework.py [DDRP-10699](https://jira.cec.lab.emc.com/browse/DDRP-10699).
- Fix PyJWT twistlock vulnerability [DDRP-10714](https://jira.cec.lab.emc.com/browse/DDRP-10714).

## v2.2.1

- Fix twistlock vulnerability [DDRP-10703](https://jira.cec.lab.emc.com/browse/DDRP-10703).

## v2.2.0

- Add Github Check-run APIs [DDRP-7754](https://jira.cec.lab.emc.com/browse/DDRP-7754).
- Move common functions in Github API class to utils.py file [DDRP-9408](https://jira.cec.lab.emc.com/browse/DDRP-9408).
- Support kafka producer to send json [DDRP-10095](https://jira.cec.lab.emc.com/browse/DDRP-10095).
- Consumer can pause and resume message processing [DDRP-10230](https://jira.cec.lab.emc.com/browse/DDRP-10230).
- Add shutdown method [DDRP-10311](https://jira.cec.lab.emc.com/browse/DDRP-10311).
- Fix twistlock vulnerability [DDRP-10661](https://jira.cec.lab.emc.com/browse/DDRP-10661).
- Add README for building drp-uspycommon-builder container [DDT-2107](https://jira.cec.lab.emc.com/browse/DDT-2107).

## v2.1.4

- Changes to handle request exception when PR files are deleted [DDT-2071](https://jira.cec.lab.emc.com/browse/DDT-2071).

## v2.1.3

- Changes to raise request exception locally [DDT-2025](https://jira.cec.lab.emc.com/browse/DDT-2025).

## v2.1.2

- Eliminate extra GitHub API calls to implement rate limit [DDRP-8735](https://jira.cec.lab.emc.com/browse/DDRP-8735).
- Consumer will collect LAG for Prometheus [DDRP-9375](https://jira.cec.lab.emc.com/browse/DDRP-9375).
- Job manager supports dynamic change of command/args for initContainers [DDRP-9671](https://jira.cec.lab.emc.com/browse/DDRP-9671).
- Update exception handler to raise original exception [DDT-1462](https://jira.cec.lab.emc.com/browse/DDT-1462).

## v2.1.1

- DEPLOYMENT_NAMESPACE, IMAGE_VERSION and POD_NAME are removed from logger [DDRP-6929](https://jira.cec.lab.emc.com/browse/DDRP-6929).
- Kafka authentication support with provided certificate and private key [DDRP-8868](https://jira.cec.lab.emc.com/browse/DDRP-8868).
- Allow creation of framework with provided configuration instead of using config directory [DDRP-9161](https://jira.cec.lab.emc.com/browse/DDRP-9161).
- get_secret function is able to read and return multiple lines for a secret [DDRP-9162](https://jira.cec.lab.emc.com/browse/DDRP-9162).
- Job manager supports dynamic update of container image and command in job config [DDRP-9289](https://jira.cec.lab.emc.com/browse/DDRP-9289).
- Logger is created before creation of ConfigurationManager instance [DDT-1479](https://jira.cec.lab.emc.com/browse/DDT-1479).
- Kafka consumer will commit message after filter and handlers are called [DDT-1480](https://jira.cec.lab.emc.com/browse/DDT-1480).
- Kafka consumer cannot be started due to slow traffic [DDT-1564](https://jira.cec.lab.emc.com/browse/DDT-1564).

## v2.1.0

- Add Github APIs [DDRP-7234](https://jira.cec.lab.emc.com/browse/DDRP-7234).

### Note
- Framework 2.1.0 contains GitHub API and that requires a github section in the configuration. Presence of github section triggers the framework to initialize the GitHubAPI module and to look for other (name, value) pairs under the github section. Many existing microservices has a github section although they don't need to use GitHub API and therefore, they don't have the required (name,value) pairs present underneath.
Recommendation - When migrating to the framework latest version (currently, 2.1.0), if a microservice has a github section but does not need to use the GitHub API, please rename it.

## v2.0.1

- Add previously missed dependencies.
- Update certifi version to 2023.7.22 to eliminate twistlock vulnerability [DDT-1442].

## v2.0.0

v2.0.0 is a feature release with the following features, fixes and enhancements:

- Job manager uses Kubernetes Watch function to monitor jobs to decrease load on the Kubernetes APIServer.
- Kafka flow control based on the maximum number of running jobs. KafkaConsumer will pause temporarily when the number of running jobs, spawned by this microservice, exceeds the value, specified in `max_parallel_job`. KafkaConsumer will resume when when the running job count decreases below the value.
- Allow user to specify job name.

## v1.0.1

v1.0.1 is a maintenance release with the following fixes:

## Fixes

- Fix Kafka offset validation failure in get_last_kafka_messages() when all messages are purged from topic.

## v1.0.0

v1.0.0 is a feature release with the following features, fixes and enhancements:

- Changed isgkafka backend library from kafka-python to confluent-kafka-python.
- check_missing_topic flag is no longer supported in each kafka consumer setting.

### Upgrade instructions

- Remove check_missing_topic flag from each kafka consumer setting if used.
- Use message.topic() and message.value() to retrieve actual topic and data payload.
