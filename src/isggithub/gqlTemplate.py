from string import Template


gqlRepoBranchProtectionDetails = Template(
    """
query {
    organization(login: $org_name){
        login
        repository(name: $repo_name){
            databaseId
            id
            branchProtectionRules (first: 100, $cursor) {
                totalCount
                edges {
                    node {
                        creator {
                            login
                        }
                        id
                        pattern
                        requiresStatusChecks
                        requiresStrictStatusChecks
                        requiredApprovingReviewCount
                        requiredStatusCheckContexts
                        reviewDismissalAllowances(first:100){
                            nodes {
                                actor {
                                    __typename
                                    ... on User {
                                        id
                                    }
                                    ... on Team {
                                        id
                                    }
                                }
                            }
                        }
                        pushAllowances (first:100)  {
                            nodes {
                                actor {
                                    __typename
                                    ... on User {
                                        id
                                    }
                                    ... on App {
                                        id
                                    }
                                    ... on Team {
                                        id
                                    }
                                }
                            }
                        }
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
    }
}
"""
)


gqlRepoCollaboratorsDetails = Template(
    """
query {
    organization(login: $org_name){
        login
        repository(name: $repo_name){
            databaseId
            id
            name
            collaborators(affiliation:DIRECT, first: 100, $cursor){
                totalCount
                edges{
                    permission
                    node {
                        login
                        name
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
    }
}
"""
)
