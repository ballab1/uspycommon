#!/bin/bash

############################################################################
# This utility script will determine the version to use for CI job building
# and uploading drp-package-uspycommon to DRP Pypi repo.
############################################################################

function get_latest()
{
    # Need regex pattern in the form of ^N[\.]N[\.]N
    version_to_search='^'$1
    version_to_search=${version_to_search//./[\\\.]}

    json_data=$(curl -s ${DRP_PYPI_REST_URL}/${PACKAGE_NAME})
    if [[ -n "$(echo ${json_data} | grep -E 'Not Found')" ]]; then
       echo ${1}
    else
       version_list=( $( echo ${json_data} | jq -r '.children[] | select(.folder==true) |.uri' | sort) )
       if [[ -n "$version_list" ]]; then
	  version_list=(${version_list[@]/?/})
	  # Find the version that matches version regex
          found_list=( $( printf '%s\n' "${version_list[@]}" | grep $version_to_search ) )
          # Get the last entry from the found_list array
          echo ${found_list[-1]}
       else
	  echo ${1}
       fi
    fi
}

function main()
{
    top_dir=$(dirname $( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P ))
    PACKAGE_NAME=${PACKAGE_NAME:-$(grep -E '^name' ${top_dir}/setup.cfg | sed -E -e 's|^name\s*=\s*(.+)$|\1|')}
    DRP_PYPI_REST_URL=${DRP_PYPI_REST_URL:-http://10.152.183.135:3141/testuser/simple}
    # The new version will be retrieved from the value, specified in the setup.cfg file. If user wants to change version, please update the value in setup.cfg file.
    new_version=${CURRENT_VERSION:-$(grep -E '^version' ${top_dir}/setup.cfg | sed -E -e 's|^version\s*=\s*(.+)$|\1|')}
    branch_name=${BRANCH_NAME:-main}

    # TO-DO: Dynamic version generation - to be done later.
#    if [[ "${branch_name}" =~ ^main$ || "${branch_name}" =~ ^staging$ ]]; then
#       # For main and staging branch, use the version specified in setup.cfg
#       new_version=${curr_version}
#    else
#       sha_id=$(git rev-parse HEAD | awk '{print substr($1,1,10)}')
#       # Get the latest version in Pypi repo which matches the version in setup.cfg
#       last_uploaded_version=$(get_latest "${curr_version}")
#
#       if [[ -z "${last_uploaded_version}" ]]; then
#	  # If none, create a new one in the format of N.N.N.dev1+g<SHA>
#	  new_version=${curr_version}".dev1+g"${sha_id}
#       else
#	  if [[ $last_uploaded_version == *"dev"* ]]; then
#	     IFS=.+ read -r -a verArr  <<< "$last_uploaded_version"
#	     dev_element=( $(printf '%s\n' "${verArr[@]}" | grep 'dev') )
#	     dev_version=${dev_element[0]#*dev}
#	     # Increment the devN part of the version
#	     new_ver=$((dev_version+1))
#	     new_version=${curr_version}".dev"${new_ver}"+g"${sha_id}
#          else
#	     new_version=${last_uploaded_version}".dev1+g"${sha_id}
#          fi
#       fi
#    fi

    sed -i "s/version.*/version = ${new_version}/" ${top_dir}/setup.cfg
    echo "${new_version}"
}

main "$@"
