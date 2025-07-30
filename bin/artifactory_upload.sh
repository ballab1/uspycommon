#!/bin/bash -e

die() {
    echo "ERROR: $*"
    exit 1
}

usage ()
{
    cat << %%
Upload artifacts to Artifactory .

USAGE:
    $THIS <-t target_folder> <-a artifact> [<-p property_string>] [<-r remote_name>]

    -c                              - Use artifactory API "Check sum Search" and "Copy Item"
                                      briefly - when we expect repository with multiple duplicates - like
                                      trident-integration/malka/operation-environment we might consider use this API
                                      as instead of copy duplicates over network - we only send SHA1 and MD5 and file's content prefix
                                      Search file in artifactory and if found use Artifcatory Copy else upload file regulary
                                      see 1) https://www.jfrog.com/confluence/display/JFROG/Artifactory+REST+API#ArtifactoryRESTAPI-ChecksumSearch
                                          2) https://www.jfrog.com/confluence/display/JFROG/Artifactory+REST+API#ArtifactoryRESTAPI-CopyItem
                                     Pros: very quick - both API in sequence take less than a 3 seconds for 0.5GB file
                                           => much quicker (300% better) than bellow "Deploy Artifact by Checksum"
                                     Cons: well need to use 2 APIs - more error prone

    -d                              - Use artifactory API "Deploy Artifact by Checksum"
                                      briefly - when we expect repository with multiple duplicates - like
                                      trident-integration/malka/operation-environment we might consider use this API
                                      as instead of copy duplicates over network - we only send SHA1 and MD5 and file's content prefix
                                      see 1) https://www.jfrog.com/confluence/display/JFROG/Artifactory+REST+API#ArtifactoryRESTAPI-DeployArtifactbyChecksum
                                      Pros: single API - pretty quick if file present
                                      Cons: seems starting data transmission prior to verififcation that file present in Artifactory
                                            so we do pay here a significant traffic bill

    -t <target_folder>              - target folder in the Artifactory to save artifacts to
    -a <artifact>                   - artifact (full name) to upload to artifactory
    -p <property_string>            - artifact property string. example: ";p1=v1;p2=v2"
    -r <remote_name>                - save the artifact on target folder by this name
    -C                              - Use a curl operation to upload instead of using the jfrog cli
    -h                              - This help
EXAMPLE:
    $THIS -t third_party -a outputs/artifacts/sdnas.docker -r sdnas.docker.remote
%%
    exit 1
}

#####################  MAIN  #####################
THIS="$(basename "$0")"
CURL="curl --user $DEVOPS_ARTIFACTORY_USER:$DEVOPS_ARTIFACTORY_PASSWORD -L --retry-connrefused --retry 5 --retry-delay 2"
JFROG_DOCKER="${DEVOPS_ARTIFACTORY_SERVER}/jfrog/jfrog-cli-v2"
JFROG_CMD="jfrog rt upload --flat --quiet --retries 5 --user $DEVOPS_ARTIFACTORY_USER --password $DEVOPS_ARTIFACTORY_PASSWORD --url https://$DEVOPS_ARTIFACTORY_SERVER/artifactory"
target=""
artifact=""
properties=""
artifact_remote_name=""
deploy_by_checksum=no
search_and_copy=no
use_curl=no

while getopts "cdt:a:p:r:Ch" flag; do
    case "$flag" in
        # Use sed to remove extra / from input strings
        c) search_and_copy=yes;;
        d) deploy_by_checksum=yes;;
        t) target="$(sed 's/\/\+/\//g;s/^\/\|\/$//g' <<< "$OPTARG")";
           [[ "$target" =~ ^artifactory/* ]] || target="artifactory/$target";
           # first dir is a target_repo
           # i.e. target=artifactory/trident-integration/malka/x.tgz  so target_repo=trident-integration
           target_repo=${target#artifactory/}; target_repo=${target_repo%%/*} ;;
        a) artifact="$(sed 's/\/\+/\//g' <<< "$OPTARG")";;
        p) properties="$OPTARG";;
        r) artifact_remote_name="$(sed 's/\/\+/\//g;s/^\/\|\/$//g' <<< "$OPTARG")";;
        C) use_curl=yes;;
        h|?) usage;;
    esac
done

[[ -z "$target" ]] && die "target should not be empty"
[[ -z "$artifact" ]] && die "Missing artifact"
[[ ! -f "$artifact" ]] && die "File $artifact does not exist"

echo "Running: $0 $*"

[[ -z $artifact_remote_name ]] && artifact_remote_name="$(basename "$artifact")"

# First make sure we do not ovveride artifact that already there
HTTP_STATUS="$($CURL -o /dev/null --silent --head --write-out '%{http_code}\n' "${DEVOPS_ARTIFACTORY_SERVER}/${target}/$artifact_remote_name")" || \
    die "Failed: test the presence of ${DEVOPS_ARTIFACTORY_SERVER}/${target}/$artifact_remote_name curl_exit=$?"

[[ "$HTTP_STATUS" != "404" ]] && echo "Skip uploading artifact since ${target}/$artifact_remote_name already exists in Artifactory." && exit 0

if [[ $search_and_copy == yes ]]; then
    MD5=$(md5sum "$artifact" | awk '{print $1}') ;

    # Note that we use &repos=${target_repo} in search query
    # Also Artifactory allows to copy objects between different repos we skip this
    # since benefit is small but a multi-repo locking and mapping [virtual/watcher repo] to [local repo] is a great headache...
    SEARCH_RESULT="$($CURL --silent --header  "X-Result-Detail:info" -X GET  \
                  "${DEVOPS_ARTIFACTORY_SERVER}/artifactory/api/search/checksum?md5=${MD5}&repos=${target_repo}")" || \
        die "Failed: api/search/checksum?md5=${MD5}&repos=${target_repo} curl_exit=$?"

    if [[ "${SEARCH_RESULT}" =~ ${DEVOPS_ARTIFACTORY_SERVER} ]]; then
        # result is json array (it could be more than one copy of the same file) - with jq we take the last uri
        src_uri="$(jq -r '.[]|.[-1].uri' <<< "${SEARCH_RESULT}")"
        # get rid of API prefix - leave only Artifactory internal path
        src_uri="${src_uri#*api/storage/}"; src_uri_repo="${src_uri%%/*}"

        copy_destination="${target#artifactory/}/$artifact_remote_name"
        copy_msg_body="Artifactory Copy Item from duplicate object ${src_uri}"
        if [[ "$target_repo" != "${src_uri_repo}" ]]; then
            # Since search done on $target_repo it means that we were searching on VIRTUAL REPO (WATCHER REPO)
            # Copy Item API is not able to choose which local repository it should copy item to ( I say - "-1" for this to Artifcatory engineer's karma)
            # So enforce the local repo to be the same one where we have found the duplicate object
            copy_destination="${copy_destination/"$target_repo"/"${src_uri_repo}"}"
        fi
        HTTP_STATUS="$($CURL -o /dev/null --silent --write-out '%{http_code}\n' \
                    -X POST "${DEVOPS_ARTIFACTORY_SERVER}/artifactory/api/copy/${src_uri}?to=${copy_destination}" )" ||\
           die "Failed: $copy_msg_body curl_exit=$?"
        if [[ "$HTTP_STATUS" != "200" ]]; then
            echo "Warning: $copy_msg_body return status ${HTTP_STATUS}"
            HTTP_STATUS=404 # Ovveride http_status for futher processing
        else
            echo "INFO: Succeeded $copy_msg_body"
            if [[ -n "$properties" ]]; then
                # Convert ";p1=v1;p2=ki;p3=v3" to "{\"props\": {\"p1\":\"v1\",\"p2\":\"ki\",\"p3\":\"v3\"}}"
                # see https://www.jfrog.com/confluence/display/JFROG/Artifactory+REST+API#ArtifactoryRESTAPI-UpdateItemProperties
                update_msg_body="Artifactory Update Item Properties for ${copy_destination}"
                properties_json="$(echo -n "$properties"| sed 's/^;/{\"props\": {\"/;  s/=/\":\"/g;  s/;/\",\"/g; s/$/\"}}/')"
                HTTP_STATUS="$($CURL -o /dev/null --silent --write-out '%{http_code}\n' \
                    -X PATCH -H "Content-Type: application/json" -d "$properties_json"  "${DEVOPS_ARTIFACTORY_SERVER}/artifactory/api/metadata/${copy_destination}" )" ||\
                   die "Failed: $update_msg_body curl_exit=$?"
                if [[ "$HTTP_STATUS" -ge 300 || "$HTTP_STATUS" -lt 200 ]]; then
                    die "Failed: $update_msg_body return status ${HTTP_STATUS}"
                fi
            fi
        fi
    fi
fi

if [[ $deploy_by_checksum == yes ]]; then
    MD5=$(md5sum "$artifact" | awk '{print $1}') ;
    SHA1=$(shasum -a 1 "$artifact" | awk '{print $1}');
    HTTP_STATUS="$($CURL -o /dev/null --write-out '%{http_code}\n' \
                  --header "X-Checksum-Deploy:false" --header "X-Checksum-MD5:${MD5}" --header "X-Checksum-Sha1:${SHA1}" \
                  --upload-file "$artifact" "${DEVOPS_ARTIFACTORY_SERVER}/${target}/$artifact_remote_name${properties}")" || \
        die "Failed: deploy by checksum for $artifact curl_exit=$?"
    # Status 201 means all worked OK here
    if [[ "$HTTP_STATUS" != "201" ]]; then
        echo "Warning: Artifactory return status $HTTP_STATUS on Checksum-Deploy of $artifact to ${target#artifactory}/$artifact_remote_name"
        HTTP_STATUS=404 # Ovveride http_status for futher processing
    fi
fi

if [[ "$HTTP_STATUS" == "404" ]]; then
    if [[ $use_curl == yes ]]; then
        $CURL -X PUT -T "${artifact}" "${DEVOPS_ARTIFACTORY_SERVER}/${target}/$artifact_remote_name${properties}" || \
            die "Failed: curl upload artifact $artifact curl_exit=$?"
    else
        artifact_realpath="$(realpath $artifact)"
        docker run -v /etc/pki:/etc/pki -v /etc/ssl/certs:/etc/ssl/certs -v $artifact_realpath:$artifact_realpath -t --rm $JFROG_DOCKER \
               $JFROG_CMD ${properties:+--target-props "$properties"} "$artifact_realpath" "${target#artifactory/}/$artifact_remote_name" || \
            die "Failed: jfrog upload artifact $artifact curl_exit=$?"
    fi
    echo ""
fi

HTTP_STATUS="$($CURL -o /dev/null --silent --head --write-out '%{http_code}\n' "${DEVOPS_ARTIFACTORY_SERVER}/${target}/$artifact_remote_name")" || \
    die "Failed: upload finished but query fails for ${DEVOPS_ARTIFACTORY_SERVER}/${target}/$artifact_remote_name curl_exit=$?"

[[ "$HTTP_STATUS" == "200" ]] && exit 0
die "Failed to find remotely artifact ${DEVOPS_ARTIFACTORY_SERVER}/${target}/$artifact_remote_name"
##########################################################################
