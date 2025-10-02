#!/bin/bash

echo "Starting post-build tasks: generating 'What to Test' notes and posting Jira comments."

# Step 1: Collect commit messages from PR range
COMMIT_MESSAGES=$(git log "$CI_PULL_REQUEST_TARGET_COMMIT".."$CI_PULL_REQUEST_SOURCE_COMMIT" --pretty=format:"%s")

# Step 2: Check if build succeeded and archive is available
if [[ -d "$CI_APP_STORE_SIGNED_APP_PATH" ]]; then

  # Step 3: Create 'What to Test' file for TestFlight
  WHAT_TO_TEST_DIR="$CI_PRIMARY_REPOSITORY_PATH/TestFlight/"
  mkdir -p "$WHAT_TO_TEST_DIR"

  WHAT_TO_TEST_FILE="$WHAT_TO_TEST_DIR/WhatToTest.en-US.txt"
  if [[ "$CI_WORKFLOW" == "Release" ]]; then
    echo "Release candidate." > "$WHAT_TO_TEST_FILE"
  elif [[ -n "$CI_PULL_REQUEST_SOURCE_BRANCH" ]]; then
    echo "$COMMIT_MESSAGES" > "$WHAT_TO_TEST_FILE"
  else
    echo "This is a refreshed staging build." > "$WHAT_TO_TEST_FILE"
  fi

  # Step 4: Jira authentication and base URL
  JIRA_EMAIL="$JIRA_USER_EMAIL"
  JIRA_API_TOKEN="$JIRA_API_TOKEN"
  JIRA_AUTH="$JIRA_EMAIL:$JIRA_API_TOKEN"
  JIRA_BASE_URL="https://aesthetics-ai.atlassian.net/rest/api/3/issue"

  # Step 5: Validate Jira API token before posting comments
  VALIDATION_RESPONSE=$(curl -s -w "%{http_code}" -o validation_body.json -u "$JIRA_AUTH" -H "Content-Type: application/json" "https://aesthetics-ai.atlassian.net/rest/api/3/myself")

  VALIDATION_STATUS="$VALIDATION_RESPONSE"

  if [[ "$VALIDATION_STATUS" == "401" ]]; then
    echo "WARNING: Jira API token is invalid or expired."

    # Append notification to WhatToTest.en-US.txt
    {
      echo ""
      echo "P.S. The Jira API token used for automated comments is invalid or expired. Please notify the developers to regenerate the JIRA_API_TOKEN here https://id.atlassian.com/manage-profile/security/api-tokens"
      echo "P.P.S. No comments with the build number were added to the Jira tasks listed above."
    } >> "$WHAT_TO_TEST_FILE"

    echo "Notification added to WhatToTest.en-US.txt"
    exit 0
  fi

  # Step 6: Parse Jira task keys directly from COMMIT_MESSAGES
  JIRA_KEYS=$(echo "$COMMIT_MESSAGES" | grep -oE "[A-Z]{2,5}-[0-9]+" | sort -u)

  if [[ -z "$JIRA_KEYS" ]]; then
    echo "No Jira task keys found in commit messages. Nothing to update in Jira."
    exit 0
  fi

  # Step 7: Define allowed statuses (case-sensitive from Jira)
  ALLOWED_STATUSES=("in progress" "code review" "ready for sandbox deployment" "ready for sandbox testing" "in sandbox testing" "sandbox testing passed" "ready for dev deploy" "ready for dev deployment" "ready for dev testing" "in dev testing" "ready for staging deployment" "ready for staging testing" "in staging testing" "ready for production deployment" "ready for production testing" "in production testing" "qa blocked" "blocked" "on hold" "reopened")


  # Step 8: Set up the comment in ADF format
  APP_NAME="A360 Scribe"
  BUILD_NUMBER="$CI_BUILD_NUMBER"
  COMMENT="$APP_NAME Build $BUILD_NUMBER
Commits:
$COMMIT_MESSAGES"

  # Step 9: Loop through Jira keys and post comments based on status
  for KEY in $JIRA_KEYS; do

    # Get issue details silently
    ISSUE_RESPONSE=$(curl -s -u "$JIRA_AUTH" -H "Content-Type: application/json" "$JIRA_BASE_URL/$KEY")

    # Extract current status
    CURRENT_STATUS=$(echo "$ISSUE_RESPONSE" | jq -r '.fields.status.name')

    # Check if current status is allowed (case-sensitive match)
    IS_ALLOWED=false
    CURRENT_LOWER=$(echo "$CURRENT_STATUS" | tr '[:upper:]' '[:lower:]')
    for STATUS in "${ALLOWED_STATUSES[@]}"; do
      STATUS_LOWER=$(echo "$STATUS" | tr '[:upper:]' '[:lower:]')
      if [[ "$CURRENT_LOWER" == "$STATUS_LOWER" ]]; then
        IS_ALLOWED=true
        break
      fi
    done

    if [[ "$IS_ALLOWED" == true ]]; then

      # ADF-compliant JSON comment payload
      JSON_PAYLOAD=$(jq -n --arg text "$COMMENT" '{"body":{"type":"doc","version":1,"content":[{"type":"paragraph","content":[{"type":"text","text":$text}]}]}}')

      RESPONSE=$(curl -s -w "%{http_code}" -o response_body.json -X POST \
        -u "$JIRA_AUTH" \
        -H "Content-Type: application/json" \
        --data "$JSON_PAYLOAD" \
        "$JIRA_BASE_URL/$KEY/comment")

      HTTP_STATUS="$RESPONSE"

      if [[ "$HTTP_STATUS" == "201" ]]; then
        echo "Comment posted to $KEY: $COMMENT"
      else
        echo "Failed to post comment to $KEY (HTTP $HTTP_STATUS)"
        echo "Response body:"
        cat response_body.json
      fi

    else
      echo "Skipping $KEY (status: '$CURRENT_STATUS')"
    fi
  done

  echo "Post-build Jira updates completed."

else
  echo "Build was not successful or archive not found. Skipping 'What to Test' notes and Jira comments."
fi
